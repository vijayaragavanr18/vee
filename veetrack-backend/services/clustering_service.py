import logging
import numpy as np
import hdbscan
from datetime import datetime, timedelta
from sqlalchemy.future import select
from sqlalchemy import desc

from database import async_session_factory
from models import ClusterVersion, ClusterAssignment, Article
from services.faiss_service import faiss_service

logger = logging.getLogger(__name__)

class ClusteringService:
    async def get_latest_version(self, session) -> ClusterVersion:
        result = await session.execute(select(ClusterVersion).order_by(desc(ClusterVersion.created_at)).limit(1))
        return result.scalar_one_or_none()

    async def run_window(self):
        """Runs the windowed clustering with versioned snapshots on the last 24h of data."""
        logger.info("Running daily HDBSCAN clustering window...")
        now = datetime.utcnow()
        window_start = now - timedelta(hours=24)
        
        async with async_session_factory() as session:
            # Create new version
            version = ClusterVersion(window_start=window_start, window_end=now)
            session.add(version)
            await session.commit()
            await session.refresh(version)
            
            # Fetch articles from last 24h
            result = await session.execute(
                select(Article.id).where(Article.published_at >= window_start)
            )
            article_ids = result.scalars().all()
            
            if len(article_ids) < 5:
                logger.warning("Not enough articles to cluster. Skipping window.")
                return

            # In reality, fetch embeddings for these from DB or FAISS
            # For this example, we mock the embeddings fetch
            # embeddings = fetch_embeddings(article_ids)
            embeddings = np.random.rand(len(article_ids), 384).astype('float32')
            
            clusterer = hdbscan.HDBSCAN(min_cluster_size=3, metric="euclidean")
            labels = clusterer.fit_predict(embeddings)
            
            # Calculate centroids and save assignments
            unique_labels = set(labels)
            for label in unique_labels:
                if label == -1:
                    continue # Noise
                    
                # Find articles in this cluster
                indices = np.where(labels == label)[0]
                cluster_embeddings = embeddings[indices]
                centroid = np.mean(cluster_embeddings, axis=0)
                
                for idx in indices:
                    assignment = ClusterAssignment(
                        version_id=version.id,
                        article_id=article_ids[idx],
                        cluster_id=int(label),
                        centroid=centroid.tobytes()
                    )
                    session.add(assignment)
                    
            await session.commit()
            logger.info(f"Clustering window completed. Version {version.id} created.")

    async def assign_to_existing(self, article_id: str, embedding: np.ndarray):
        """Appends a new article to the nearest existing cluster centroid from the current version."""
        async with async_session_factory() as session:
            latest_version = await self.get_latest_version(session)
            if not latest_version:
                return None
                
            # Fetch all centroids for the latest version
            # (In production, this could be cached in memory)
            result = await session.execute(
                select(ClusterAssignment.cluster_id, ClusterAssignment.centroid)
                .where(ClusterAssignment.version_id == latest_version.id)
                .distinct()
            )
            centroids_data = result.all()
            
            if not centroids_data:
                return None
                
            best_cluster = -1
            best_sim = -1.0
            
            # Simple cosine similarity to centroids
            for c_id, centroid_bytes in centroids_data:
                if centroid_bytes:
                    centroid = np.frombuffer(centroid_bytes, dtype=np.float32)
                    sim = np.dot(embedding, centroid) / (np.linalg.norm(embedding) * np.linalg.norm(centroid))
                    if sim > best_sim:
                        best_sim = sim
                        best_cluster = c_id
                        
            if best_sim > 0.85: # Threshold to join cluster
                assignment = ClusterAssignment(
                    version_id=latest_version.id,
                    article_id=article_id,
                    cluster_id=best_cluster,
                    centroid=None # Inherit cluster centroid implicitly
                )
                session.add(assignment)
                await session.commit()
                return best_cluster
            
            return None

    async def get_trending(self):
        """Reads trending topics from current version."""
        async with async_session_factory() as session:
            latest_version = await self.get_latest_version(session)
            if not latest_version:
                return []
                
            # Aggregate clusters by count
            # select cluster_id, count(article_id) group by cluster_id
            return [{"cluster_id": 1, "article_count": 42}] # Mocked response

clustering_service = ClusteringService()
