#!/usr/bin/env python3
import hashlib
import sqlite3
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF


def _uri(kind: str, value: str) -> URIRef:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return URIRef(f"https://example.org/nas/{kind}/{digest}")

def build_rdf_graph(db_path: Path, output_ttl: Path):
    """Builds the RDF Knowledge Graph from production_inventory."""
    g = Graph()
    NAS = URIRef("https://example.org/nas/")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT id, nextcloud_path, file_size FROM production_inventory")
    
    count = 0
    for row in cursor.fetchall():
        path = str(row["nextcloud_path"])
        filename = path.split("/")[-1]
        parent_path = path.rsplit("/", 1)[0]
        
        file_uri = _uri("file", path)
        parent_uri = _uri("folder", parent_path)
        
        g.add((file_uri, RDF.type, URIRef(f"{NAS}File")))
        g.add((file_uri, URIRef(f"{NAS}path"), Literal(path)))
        g.add((file_uri, URIRef(f"{NAS}filename"), Literal(filename)))
        g.add((file_uri, URIRef(f"{NAS}locatedIn"), parent_uri))
        g.add((parent_uri, RDF.type, URIRef(f"{NAS}Folder")))
        
        # Mark as KG Indexed
        conn.execute("UPDATE production_inventory SET kg_indexed = 1 WHERE id = ?", (row["id"],))
        count += 1
        
    output_ttl.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=output_ttl, format="turtle")
    conn.commit()
    conn.close()
    
    print(f"✅ Knowledge Graph built: {count} entities exported to {output_ttl}")