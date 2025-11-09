"""
Maximum Spanning Tree (MST) calculation for browser tab graphs.

Provides algorithms to compute maximum spanning trees using a hybrid approach:
- Calculates MST within each cluster (strongest intra-cluster connections)
- Finds bridge edges between clusters (strongest inter-cluster connections)
- Identifies central/important nodes based on MST structure

This creates a cleaner graph structure by keeping only the most important edges.
"""

from typing import List, Dict, Set, Tuple, Optional
import heapq
from dataclasses import dataclass


@dataclass
class Edge:
    """Represents a weighted edge in the graph"""
    node1: int
    node2: int
    weight: float

    def __lt__(self, other):
        # For max heap, we want higher weights first
        return self.weight > other.weight

    def __repr__(self):
        return f"Edge({self.node1} <-> {self.node2}, weight={self.weight:.3f})"


@dataclass
class MSTResult:
    """Results from MST calculation"""
    edges: List[Edge]
    total_weight: float
    cluster_msts: Dict[int, List[Edge]]  # cluster_id -> edges in that cluster's MST
    bridge_edges: List[Edge]  # edges connecting different clusters
    node_centrality: Dict[int, float]  # node_id -> centrality score

    def __repr__(self):
        return (f"MSTResult(edges={len(self.edges)}, "
                f"total_weight={self.total_weight:.3f}, "
                f"clusters={len(self.cluster_msts)}, "
                f"bridges={len(self.bridge_edges)})")


class UnionFind:
    """Union-Find (Disjoint Set) data structure for cycle detection"""

    def __init__(self, nodes: List[int]):
        self.parent = {node: node for node in nodes}
        self.rank = {node: 0 for node in nodes}

    def find(self, node: int) -> int:
        """Find root of node with path compression"""
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])
        return self.parent[node]

    def union(self, node1: int, node2: int) -> bool:
        """Union two sets. Returns True if they were merged, False if already connected"""
        root1 = self.find(node1)
        root2 = self.find(node2)

        if root1 == root2:
            return False  # Already in same set (would create cycle)

        # Union by rank
        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1

        return True


class SpanningTreeCalculator:
    """Calculates maximum spanning trees for tab graphs"""

    def __init__(self, min_edge_weight: float = 0.0):
        """
        Initialize the spanning tree calculator.

        Args:
            min_edge_weight: Minimum edge weight to consider (default: 0.0)
                           Edges below this weight are ignored
        """
        self.min_edge_weight = min_edge_weight

    def calculate_mst(
        self,
        nodes: List[int],
        edges: List[Edge],
        clusters: Optional[Dict[int, int]] = None
    ) -> MSTResult:
        """
        Calculate maximum spanning tree with hybrid approach.

        Args:
            nodes: List of node IDs
            edges: List of Edge objects with weights
            clusters: Optional dict mapping node_id -> cluster_id

        Returns:
            MSTResult containing MST edges, cluster MSTs, bridges, and centrality
        """
        if not nodes:
            return MSTResult([], 0.0, {}, [], {})

        # Filter edges by minimum weight
        edges = [e for e in edges if e.weight >= self.min_edge_weight]

        if clusters is None:
            # No clusters - simple maximum spanning tree
            mst_edges = self._kruskal_maximum(nodes, edges)
            centrality = self._calculate_centrality(nodes, mst_edges)

            return MSTResult(
                edges=mst_edges,
                total_weight=sum(e.weight for e in mst_edges),
                cluster_msts={},
                bridge_edges=[],
                node_centrality=centrality
            )

        # Hybrid approach: per-cluster MSTs + bridges
        cluster_msts = {}
        all_mst_edges = []

        # 1. Calculate MST for each cluster
        for cluster_id in set(clusters.values()):
            cluster_nodes = [n for n in nodes if clusters.get(n) == cluster_id]

            if len(cluster_nodes) < 2:
                cluster_msts[cluster_id] = []
                continue

            # Filter edges to only include edges within this cluster
            cluster_edges = [
                e for e in edges
                if clusters.get(e.node1) == cluster_id and clusters.get(e.node2) == cluster_id
            ]

            # Calculate MST for this cluster
            mst = self._kruskal_maximum(cluster_nodes, cluster_edges)
            cluster_msts[cluster_id] = mst
            all_mst_edges.extend(mst)

        # 2. Find bridge edges between clusters
        bridge_edges = self._find_bridge_edges(edges, clusters)
        all_mst_edges.extend(bridge_edges)

        # 3. Calculate centrality scores
        centrality = self._calculate_centrality(nodes, all_mst_edges)

        return MSTResult(
            edges=all_mst_edges,
            total_weight=sum(e.weight for e in all_mst_edges),
            cluster_msts=cluster_msts,
            bridge_edges=bridge_edges,
            node_centrality=centrality
        )

    def _kruskal_maximum(self, nodes: List[int], edges: List[Edge]) -> List[Edge]:
        """
        Kruskal's algorithm for maximum spanning tree.

        Greedily adds edges in descending order of weight without creating cycles.
        """
        if not nodes or not edges:
            return []

        # Sort edges by weight (descending for maximum spanning tree)
        sorted_edges = sorted(edges, key=lambda e: e.weight, reverse=True)

        # Initialize union-find
        uf = UnionFind(nodes)

        mst = []
        for edge in sorted_edges:
            # Try to add edge - only succeeds if it doesn't create a cycle
            if uf.union(edge.node1, edge.node2):
                mst.append(edge)

                # MST is complete when we have n-1 edges for n nodes
                if len(mst) == len(nodes) - 1:
                    break

        return mst

    def _find_bridge_edges(
        self,
        edges: List[Edge],
        clusters: Dict[int, int]
    ) -> List[Edge]:
        """
        Find the strongest bridge edge between each pair of clusters.

        Returns one edge per cluster pair (the strongest connection).
        """
        # Group inter-cluster edges by cluster pair
        cluster_pairs: Dict[Tuple[int, int], List[Edge]] = {}

        for edge in edges:
            c1 = clusters.get(edge.node1)
            c2 = clusters.get(edge.node2)

            if c1 is None or c2 is None or c1 == c2:
                continue  # Skip intra-cluster or invalid edges

            # Normalize cluster pair (smaller first)
            pair = (min(c1, c2), max(c1, c2))

            if pair not in cluster_pairs:
                cluster_pairs[pair] = []
            cluster_pairs[pair].append(edge)

        # Select strongest bridge edge for each cluster pair
        bridges = []
        for pair, pair_edges in cluster_pairs.items():
            # Get edge with maximum weight
            strongest = max(pair_edges, key=lambda e: e.weight)
            bridges.append(strongest)

        return bridges

    def _calculate_centrality(
        self,
        nodes: List[int],
        mst_edges: List[Edge]
    ) -> Dict[int, float]:
        """
        Calculate eigenvector centrality for nodes based on MST structure.

        Eigenvector centrality measures importance by considering connections
        to other important nodes. A node is central if it's connected to
        other central nodes with strong edges.

        Uses power iteration to find the principal eigenvector of the
        weighted adjacency matrix.

        Returns:
            Dict mapping node_id -> centrality_score (0.0 to 1.0)
        """
        if not nodes:
            return {}

        # Build weighted adjacency matrix
        adjacency = {node: {} for node in nodes}

        for edge in mst_edges:
            # Symmetric matrix (undirected graph)
            adjacency[edge.node1][edge.node2] = edge.weight
            adjacency[edge.node2][edge.node1] = edge.weight

        # Power iteration to compute eigenvector centrality
        max_iterations = 100
        tolerance = 1e-6

        # Initialize centrality scores uniformly
        centrality = {node: 1.0 / len(nodes) for node in nodes}

        for iteration in range(max_iterations):
            # Store previous values to check convergence
            prev_centrality = centrality.copy()

            # Update centrality: x_new[i] = sum(A[i][j] * x[j])
            new_centrality = {}
            for node in nodes:
                score = 0.0
                for neighbor, weight in adjacency[node].items():
                    score += weight * prev_centrality[neighbor]
                new_centrality[node] = score

            # Normalize to prevent overflow/underflow
            norm = sum(new_centrality.values())
            if norm > 0:
                for node in nodes:
                    new_centrality[node] /= norm
            else:
                # Handle disconnected nodes
                for node in nodes:
                    new_centrality[node] = 1.0 / len(nodes)

            centrality = new_centrality

            # Check convergence
            diff = sum(abs(centrality[node] - prev_centrality[node]) for node in nodes)
            if diff < tolerance:
                break

        # Final normalization to 0-1 range
        max_centrality = max(centrality.values()) if centrality else 1.0
        if max_centrality > 0:
            for node in nodes:
                centrality[node] /= max_centrality

        return centrality

    def get_most_central_nodes(
        self,
        mst_result: MSTResult,
        top_n: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Get the most central nodes from MST.

        Args:
            mst_result: Result from calculate_mst
            top_n: Number of top nodes to return

        Returns:
            List of (node_id, centrality_score) tuples, sorted by centrality
        """
        sorted_nodes = sorted(
            mst_result.node_centrality.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_nodes[:top_n]

    def get_cluster_central_nodes(
        self,
        mst_result: MSTResult,
        clusters: Dict[int, int],
        top_n_per_cluster: int = 3
    ) -> Dict[int, List[Tuple[int, float]]]:
        """
        Get the most central nodes per cluster.

        Args:
            mst_result: Result from calculate_mst
            clusters: Dict mapping node_id -> cluster_id
            top_n_per_cluster: Number of top nodes per cluster

        Returns:
            Dict mapping cluster_id -> list of (node_id, centrality_score) tuples
        """
        # Group nodes by cluster
        cluster_nodes: Dict[int, List[int]] = {}
        for node, cluster_id in clusters.items():
            if cluster_id not in cluster_nodes:
                cluster_nodes[cluster_id] = []
            cluster_nodes[cluster_id].append(node)

        # Get top nodes per cluster
        result = {}
        for cluster_id, nodes in cluster_nodes.items():
            # Get centrality scores for nodes in this cluster
            cluster_centrality = [
                (node, mst_result.node_centrality.get(node, 0.0))
                for node in nodes
            ]

            # Sort by centrality and take top N
            cluster_centrality.sort(key=lambda x: x[1], reverse=True)
            result[cluster_id] = cluster_centrality[:top_n_per_cluster]

        return result


# Example usage
if __name__ == "__main__":
    print("="*60)
    print("Maximum Spanning Tree Calculator - Example Usage")
    print("="*60)

    # Example graph with 3 clusters
    nodes = [0, 1, 2, 3, 4, 5, 6, 7, 8]

    # Define clusters
    clusters = {
        0: 0, 1: 0, 2: 0,  # Cluster 0
        3: 1, 4: 1, 5: 1,  # Cluster 1
        6: 2, 7: 2, 8: 2   # Cluster 2
    }

    # Example edges with weights
    edges = [
        # Cluster 0 edges (strong connections)
        Edge(0, 1, 0.9),
        Edge(1, 2, 0.85),
        Edge(0, 2, 0.8),

        # Cluster 1 edges (strong connections)
        Edge(3, 4, 0.88),
        Edge(4, 5, 0.92),
        Edge(3, 5, 0.78),

        # Cluster 2 edges (strong connections)
        Edge(6, 7, 0.87),
        Edge(7, 8, 0.90),
        Edge(6, 8, 0.82),

        # Bridge edges between clusters (weaker)
        Edge(2, 3, 0.45),  # Cluster 0 -> 1
        Edge(1, 4, 0.30),
        Edge(5, 6, 0.50),  # Cluster 1 -> 2
        Edge(4, 7, 0.35),
        Edge(0, 6, 0.25),  # Cluster 0 -> 2
    ]

    # Calculate MST
    calculator = SpanningTreeCalculator(min_edge_weight=0.2)
    result = calculator.calculate_mst(nodes, edges, clusters)

    print(f"\n{result}")
    print(f"\nTotal MST edges: {len(result.edges)}")
    print(f"Total weight: {result.total_weight:.3f}")

    # Show per-cluster MSTs
    print(f"\n{'='*60}")
    print("Per-Cluster MSTs:")
    print('='*60)
    for cluster_id, cluster_edges in result.cluster_msts.items():
        print(f"\nCluster {cluster_id} ({len(cluster_edges)} edges):")
        for edge in cluster_edges:
            print(f"  {edge}")

    # Show bridge edges
    print(f"\n{'='*60}")
    print("Bridge Edges (connecting clusters):")
    print('='*60)
    for edge in result.bridge_edges:
        c1 = clusters[edge.node1]
        c2 = clusters[edge.node2]
        print(f"  Cluster {c1} <-> Cluster {c2}: {edge}")

    # Show centrality scores
    print(f"\n{'='*60}")
    print("Node Centrality (top 5 overall):")
    print('='*60)
    top_nodes = calculator.get_most_central_nodes(result, top_n=5)
    for node, score in top_nodes:
        print(f"  Node {node}: {score:.3f} (Cluster {clusters[node]})")

    # Show per-cluster central nodes
    print(f"\n{'='*60}")
    print("Most Central Nodes per Cluster:")
    print('='*60)
    cluster_central = calculator.get_cluster_central_nodes(result, clusters, top_n_per_cluster=2)
    for cluster_id, nodes_scores in cluster_central.items():
        print(f"\nCluster {cluster_id}:")
        for node, score in nodes_scores:
            print(f"  Node {node}: {score:.3f}")

    # Example without clusters (simple MST)
    print(f"\n\n{'='*60}")
    print("Simple MST (no clusters):")
    print('='*60)
    simple_result = calculator.calculate_mst(nodes, edges, clusters=None)
    print(f"\n{simple_result}")
    print(f"Total edges: {len(simple_result.edges)}")
    for edge in simple_result.edges:
        print(f"  {edge}")
