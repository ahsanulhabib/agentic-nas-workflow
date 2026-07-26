import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
from src.kg.fuseki import FusekiClient
from src.config import load_settings

st.set_page_config(page_title="KG Viewer", layout="wide")
st.title("🕸️ Interactive Knowledge Graph")

settings = load_settings()
fuseki = FusekiClient(settings["kg"]["fuseki_url"], settings["kg"]["dataset"])

if not fuseki.health():
    st.error("Apache Jena Fuseki is offline. Check your Docker container.")
else:
    st.success("Connected to Apache Jena TDB2")
    
    query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o . } LIMIT 150"
    try:
        results = fuseki.query(query)
        bindings = results.get("results", {}).get("bindings", [])
        
        nodes_set = set()
        nodes, edges = [], []
        
        for b in bindings:
            s, p, o = b['s']['value'], b['p']['value'], b['o']['value']
            
            s_label = s.split("/")[-1][:25]
            o_label = o.split("/")[-1][:25] if "http" in o else o[:25]
            p_label = p.split("/")[-1].split("#")[-1]
            
            if s not in nodes_set:
                nodes.append(Node(id=s, label=s_label, size=20, color="#00C4B6"))
                nodes_set.add(s)
            if o not in nodes_set:
                nodes.append(Node(id=o, label=o_label, size=15, color="#FF9F1C"))
                nodes_set.add(o)
                
            edges.append(Edge(source=s, target=o, label=p_label))
            
        config = Config(width=1000, height=600, directed=True, physics=True, hierarchical=False)
        agraph(nodes=nodes, edges=edges, config=config)
        
    except Exception as e:
        st.error(f"Failed to render graph: {e}")