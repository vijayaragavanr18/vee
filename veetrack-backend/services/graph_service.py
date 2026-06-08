import os
import pickle
import logging
import networkx as nx
from sqlalchemy.future import select
from datetime import datetime

from database import async_session_factory
from models import EntityNode, EntityEdge

logger = logging.getLogger(__name__)
GRAPH_DUMP_PATH = os.getenv("GRAPH_DUMP_PATH", "/tmp/veetrack_graph.pkl")

class GraphService:
    def __init__(self):
        import asyncio
        self.G = nx.Graph()
        self.lock = asyncio.Lock()
        
    async def load(self):
        """Loads graph from pickle if exists, else from DB."""
        if os.path.exists(GRAPH_DUMP_PATH):
            try:
                with open(GRAPH_DUMP_PATH, "rb") as f:
                    self.G = pickle.load(f)
                logger.info(f"Graph loaded from disk: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges.")
                return
            except Exception as e:
                logger.error(f"Failed to load graph from pickle: {e}")
                
        # Load from DB
        logger.info("Loading graph from PostgreSQL...")
        async with async_session_factory() as session:
            # Load Nodes
            nodes_result = await session.execute(select(EntityNode))
            for n in nodes_result.scalars().all():
                self.G.add_node(n.name, type=n.type)
                
            # Load Edges
            edges_result = await session.execute(select(EntityEdge))
            for e in edges_result.scalars().all():
                self.G.add_edge(e.source, e.target, weight=e.weight, relation=e.relation_type)
                
        logger.info(f"Graph DB load complete: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges.")

    def checkpoint(self):
        """Snapshots the NetworkX graph to disk."""
        try:
            with open(GRAPH_DUMP_PATH, "wb") as f:
                pickle.dump(self.G, f)
            logger.info("Graph snapshot saved.")
        except Exception as e:
            logger.error(f"Failed to snapshot graph: {e}")

    async def add_article_entities(self, entities: list[dict]):
        """Adds entities and fully-connected co-occurrence edges to the graph."""
        async with self.lock:
            async with async_session_factory() as session:
                for e in entities:
                    name = e["text"]
                etype = e.get("label", "UNKNOWN")
                
                # Add to NetworkX
                if not self.G.has_node(name):
                    self.G.add_node(name, type=etype)
                    # Add to DB
                    db_node = EntityNode(name=name, type=etype)
                    session.add(db_node)
                else:
                    # Update last seen
                    result = await session.execute(select(EntityNode).where(EntityNode.name == name))
                    db_node = result.scalar_one_or_none()
                    if db_node:
                        db_node.last_seen = datetime.utcnow()
            
            # Create co-occurrence edges (every entity connected to every other in the same article)
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    n1 = entities[i]["text"]
                    n2 = entities[j]["text"]
                    
                    if n1 == n2:
                        continue
                        
                    if self.G.has_edge(n1, n2):
                        self.G[n1][n2]['weight'] += 1
                        
                        # Update DB edge
                        result = await session.execute(
                            select(EntityEdge).where(
                                ((EntityEdge.source == n1) & (EntityEdge.target == n2)) |
                                ((EntityEdge.source == n2) & (EntityEdge.target == n1))
                            )
                        )
                        db_edge = result.scalar_one_or_none()
                        if db_edge:
                            db_edge.weight += 1
                            db_edge.article_count += 1
                    else:
                        self.G.add_edge(n1, n2, weight=1, relation="co-occurrence")
                        db_edge = EntityEdge(source=n1, target=n2, weight=1, article_count=1)
                        session.add(db_edge)

            await session.commit()

    def get_neighbors(self, entity_name: str, limit: int = 10):
        if not self.G.has_node(entity_name):
            return []
            
        neighbors = []
        for neighbor in self.G.neighbors(entity_name):
            weight = self.G[entity_name][neighbor]['weight']
            neighbors.append({"entity": neighbor, "weight": weight})
            
        neighbors.sort(key=lambda x: x["weight"], reverse=True)
        return neighbors[:limit]

    def get_path(self, entity_a: str, entity_b: str):
        if not self.G.has_node(entity_a) or not self.G.has_node(entity_b):
            return {"error": "Entities not found in graph."}
            
        try:
            path = nx.shortest_path(self.G, source=entity_a, target=entity_b)
            return {"path": path}
        except nx.NetworkXNoPath:
            return {"error": "No connection between entities."}

graph_service = GraphService()
