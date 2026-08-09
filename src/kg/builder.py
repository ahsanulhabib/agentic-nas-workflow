from __future__ import annotations  #noqa: EXE002

import hashlib
import sqlite3
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from src.kg.namespaces import NAS, PROV, SCHEMA, SKOS


def _uri(kind: str, value: str) -> URIRef:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return URIRef(f"https://example.org/nas/{kind}/{digest}")

def build_rdf_graph(db_path: Path | str, output_ttl: Path | str) -> Graph:
    """Enterprise RDF Graph Generator with SKOS Taxonomy & PROV-O Lineage."""
    g = Graph()
    g.bind("nas", NAS)
    g.bind("schema", SCHEMA)
    g.bind("prov", PROV)
    g.bind("skos", SKOS)
    
    db_path = Path(db_path)
    output_ttl = Path(output_ttl)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, blake3_hash, nextcloud_path, file_size, ingested_at 
        FROM production_inventory
    """)
    rows = cursor.fetchall()

    graph_uri = URIRef("https://example.org/nas/graph/current")
    g.add((graph_uri, RDF.type, NAS.KnowledgeGraph))

    for row in rows:
        path = str(row["nextcloud_path"])
        filename = Path(path).name
        parent_path = str(Path(path).parent)
        file_hash = str(row["blake3_hash"])
        file_size = int(row["file_size"] or 0)

        file_uri = _uri("file", path)
        parent_uri = _uri("folder", parent_path)
        hash_uri = _uri("content", file_hash)

        # File Node
        g.add((file_uri, RDF.type, NAS.File))
        g.add((file_uri, RDF.type, SCHEMA.DigitalDocument))
        g.add((file_uri, NAS.path, Literal(path, datatype=XSD.string)))
        g.add((file_uri, NAS.filename, Literal(filename, datatype=XSD.string)))
        g.add((file_uri, SCHEMA.contentSize, Literal(file_size, datatype=XSD.integer)))
        g.add((file_uri, NAS.locatedIn, parent_uri))
        
        # PROV-O Lineage
        g.add((file_uri, PROV.wasDerivedFrom, hash_uri))
        g.add((hash_uri, RDF.type, NAS.ContentHash))
        g.add((hash_uri, NAS.hashValue, Literal(file_hash, datatype=XSD.string)))

        # Folder Node (SKOS Concept)
        g.add((parent_uri, RDF.type, NAS.Folder))
        g.add((parent_uri, RDF.type, SKOS.Concept))
        g.add((parent_uri, NAS.path, Literal(parent_path, datatype=XSD.string)))
        g.add((parent_uri, SKOS.prefLabel, Literal(Path(parent_path).name or "Root")))

        conn.execute("UPDATE production_inventory SET kg_indexed = 1 WHERE id = ?", (row["id"],))

    conn.commit()
    conn.close()

    output_ttl.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=output_ttl, format="turtle")
    return g