import json
import re
import base64
import unicodedata
import streamlit as st
import streamlit.components.v1 as components
import requests

st.set_page_config(page_title="Projeto Enem Bernoulli — fluxo", layout="wide")

DATA_PATH = "data/fluxo.json"


# --------------------------------------------------------------------------
# Carregamento e persistência (GitHub — cada salvamento vira um commit)
# --------------------------------------------------------------------------
def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_to_github(data):
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO")
    if not token or not repo:
        return False, "Faltam GITHUB_TOKEN e/ou GITHUB_REPO nas secrets do Streamlit."

    api_url = f"https://api.github.com/repos/{repo}/contents/{DATA_PATH}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    r = requests.get(api_url, headers=headers, timeout=15)
    sha = r.json().get("sha") if r.status_code == 200 else None

    content_str = json.dumps(data, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    payload = {"message": "Atualiza fluxo via Streamlit", "content": content_b64}
    if sha:
        payload["sha"] = sha

    r2 = requests.put(api_url, headers=headers, json=payload, timeout=15)
    if r2.status_code in (200, 201):
        return True, None
    return False, f"GitHub retornou {r2.status_code}: {r2.text[:200]}"


if "data" not in st.session_state:
    st.session_state.data = load_data()

data = st.session_state.data


# --------------------------------------------------------------------------
# Utilitários
# --------------------------------------------------------------------------
def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "item"


def unique_id(base, existing_ids):
    if base not in existing_ids:
        return base
    i = 2
    while f"{base}_{i}" in existing_ids:
        i += 1
    return f"{base}_{i}"


def mermaid_escape(text):
    if not text:
        return ""
    return str(text).replace('"', "'").replace("\n", " ")


# --------------------------------------------------------------------------
# Construção do texto Mermaid a partir de nós e arestas
# --------------------------------------------------------------------------
def build_mermaid(data):
    lines = ["flowchart LR"]

    for cat_id, cat in data["categorias"].items():
        stroke = cat["cor"]
        if cat_id == "marco":
            lines.append(f'classDef cat_{cat_id} fill:#2B2A24,stroke:{stroke},color:#F4EFE2,stroke-width:3px;')
        else:
            lines.append(f'classDef cat_{cat_id} fill:{stroke}22,stroke:{stroke},color:#2B2A24,stroke-width:1.5px;')

    for node_id, node in data["nos"].items():
        label_parts = [mermaid_escape(node["titulo"])]
        if node.get("responsavel"):
            label_parts.append(mermaid_escape(node["responsavel"]))
        if node.get("periodo"):
            label_parts.append(mermaid_escape(node["periodo"]))
        if node.get("pessoas"):
            label_parts.append("pessoas: " + mermaid_escape(node["pessoas"]))
        if node.get("status"):
            label_parts.append(mermaid_escape(node["status"]))
        label = "<br/>".join(label_parts)

        if node.get("categoria") == "marco":
            lines.append(f'{node_id}{{"{label}"}}:::cat_{node["categoria"]}')
        else:
            lines.append(f'{node_id}["{label}"]:::cat_{node.get("categoria", "")}')

    for edge in data["arestas"]:
        if edge["de"] not in data["nos"] or edge["para"] not in data["nos"]:
            continue
        if edge.get("rotulo"):
            lines.append(f'{edge["de"]} -->|{mermaid_escape(edge["rotulo"])}| {edge["para"]}')
        else:
            lines.append(f'{edge["de"]} --> {edge["para"]}')

    return "\n".join(lines)


BOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;}
  html,body{margin:0;padding:0;}
  body{font-family:'Inter',sans-serif; background:#EDE6D4; color:#2B2A24;}
  .legend{display:flex; flex-wrap:wrap; gap:14px; padding:14px 18px 6px;}
  .legend-item{display:flex; align-items:center; gap:6px; font-size:12px;}
  .legend-swatch{width:13px; height:13px; border-radius:3px;}
  .zoom-controls{ position:absolute; top:14px; right:18px; display:flex; gap:6px; z-index:20; }
  .zoom-btn{ width:30px; height:30px; border-radius:8px; border:1px solid #DAD2BC; background:#FFFDF6;
    color:#2B2A24; font-size:15px; cursor:pointer; }
  .zoom-btn:hover{border-color:#B7AC8C;}
  .zoom-level{ font-size:12px; color:#6B6A5F; background:#FFFDF6; border:1px solid #DAD2BC;
    border-radius:8px; padding:0 8px; display:flex; align-items:center; min-width:44px; justify-content:center; }
  .board-scroll{ position:relative; overflow:auto; height:600px;
    background-image:radial-gradient(#DFD6BE 1px, transparent 1px); background-size:14px 14px; }
  .board-zoom-wrapper{ transform-origin:0 0; padding:20px; }
  .mermaid{ background:transparent; }
</style>
</head>
<body>
  <div class="legend">__LEGEND__</div>
  <div class="board-scroll">
    <div class="zoom-controls">
      <button class="zoom-btn" id="zoom-out">&minus;</button>
      <div class="zoom-level" id="zoom-level">100%</div>
      <button class="zoom-btn" id="zoom-in">+</button>
      <button class="zoom-btn" id="zoom-reset" style="width:auto; padding:0 8px; font-size:11px;">reset</button>
    </div>
    <div class="board-zoom-wrapper" id="board-zoom-wrapper">
      <pre class="mermaid">__MERMAID__</pre>
    </div>
  </div>

<script>
  mermaid.initialize({ startOnLoad: true, theme: 'base', securityLevel: 'loose',
    themeVariables: { fontFamily: 'Inter, sans-serif', fontSize: '14px' } });

  window.addEventListener('load', function(){
    setTimeout(setupZoom, 600);
  });

  function setupZoom(){
    const svg = document.querySelector('.mermaid svg');
    const wrapper = document.getElementById('board-zoom-wrapper');
    if(!svg){ setTimeout(setupZoom, 400); return; }
    const baseWidth = wrapper.scrollWidth;
    const baseHeight = wrapper.scrollHeight;
    const levelLabel = document.getElementById('zoom-level');
    let scale = 1;
    const MIN = 0.4, MAX = 2, STEP = 0.15;

    function apply(){
      wrapper.style.transform = `scale(${scale})`;
      wrapper.style.width = baseWidth + 'px';
      wrapper.style.height = baseHeight + 'px';
      levelLabel.textContent = Math.round(scale*100) + '%';
    }
    apply();

    document.getElementById('zoom-in').addEventListener('click', ()=>{ scale = Math.min(MAX, +(scale+STEP).toFixed(2)); apply(); });
    document.getElementById('zoom-out').addEventListener('click', ()=>{ scale = Math.max(MIN, +(scale-STEP).toFixed(2)); apply(); });
    document.getElementById('zoom-reset').addEventListener('click', ()=>{ scale = 1; apply(); });

    document.querySelector('.board-scroll').addEventListener('wheel', function(e){
      if(!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      scale = e.deltaY < 0 ? Math.min(MAX, +(scale+0.08).toFixed(2)) : Math.max(MIN, +(scale-0.08).toFixed(2));
      apply();
    }, { passive:false });
  }
</script>
</body>
</html>
"""


def render_board(data):
    legend_html = "".join(
        f'<div class="legend-item"><span class="legend-swatch" style="background:{cat["cor"]}"></span>{cat["nome"]}</div>'
        for cat in data["categorias"].values()
    )
    mermaid_text = build_mermaid(data)
    html = BOARD_TEMPLATE.replace("__LEGEND__", legend_html).replace("__MERMAID__", mermaid_text)
    components.html(html, height=660, scrolling=False)


# --------------------------------------------------------------------------
# Layout da página
# --------------------------------------------------------------------------
st.title("Projeto Enem Bernoulli — fluxo operacional")
st.caption("Cada caixa é uma frente de trabalho. As setas mostram dependência entre elas. Use os botões de zoom (ou Ctrl/Cmd + scroll) para navegar.")

render_board(data)

st.divider()

with st.sidebar:
    st.header("Modo de edição")
    pw = st.text_input("Senha", type="password")
    is_editor = pw != "" and pw == st.secrets.get("EDIT_PASSWORD", None)

    if pw and not is_editor:
        st.error("Senha incorreta.")

    if is_editor:
        st.success("Modo de edição ativo.")

        def persist(msg):
            st.session_state.data = data
            ok, err = save_to_github(data)
            if ok:
                st.success(msg + " O fluxo público atualiza em cerca de 1 minuto.")
                st.rerun()
            else:
                st.error(f"Não consegui salvar no GitHub: {err}")

        tab_new_node, tab_edit_node, tab_new_edge, tab_new_cat, tab_delete = st.tabs(
            ["+ Caixa", "Editar caixa", "+ Seta", "+ Categoria", "Excluir"]
        )

        # ---------------- Adicionar caixa ----------------
        with tab_new_node:
            with st.form("new_node_form"):
                titulo = st.text_input("Título da caixa")
                cat_ids = list(data["categorias"].keys())
                cat_labels = [data["categorias"][c]["nome"] for c in cat_ids]
                cat_idx = st.selectbox("Categoria", range(len(cat_ids)), format_func=lambda i: cat_labels[i])
                responsavel = st.text_input("Responsável")
                periodo = st.text_input("Período / data")
                pessoas = st.text_input("Pessoas envolvidas (ex.: 30 professores)")
                status = st.text_input("Status (ex.: Não iniciado, 2/7)")
                descricao = st.text_area("Descrição")
                submitted = st.form_submit_button("Adicionar caixa")

            if submitted:
                if not titulo.strip():
                    st.error("Dê um título para a caixa antes de adicionar.")
                else:
                    new_id = unique_id("n_" + slugify(titulo), data["nos"].keys())
                    data["nos"][new_id] = {
                        "titulo": titulo, "categoria": cat_ids[cat_idx], "responsavel": responsavel,
                        "periodo": periodo, "pessoas": pessoas, "status": status, "descricao": descricao,
                    }
                    persist(f'Caixa "{titulo}" adicionada!')

        # ---------------- Editar caixa ----------------
        with tab_edit_node:
            node_ids = list(data["nos"].keys())
            node_labels = [data["nos"][n]["titulo"] for n in node_ids]
            idx = st.selectbox("Caixa", range(len(node_ids)), format_func=lambda i: node_labels[i], key="edit_sel")
            nid = node_ids[idx]
            node = data["nos"][nid]

            with st.form("edit_node_form"):
                cat_ids = list(data["categorias"].keys())
                cat_labels = [data["categorias"][c]["nome"] for c in cat_ids]
                cat_idx = st.selectbox(
                    "Categoria", range(len(cat_ids)), format_func=lambda i: cat_labels[i],
                    index=cat_ids.index(node.get("categoria", cat_ids[0])) if node.get("categoria") in cat_ids else 0,
                )
                responsavel = st.text_input("Responsável", value=node.get("responsavel", ""))
                periodo = st.text_input("Período / data", value=node.get("periodo", ""))
                pessoas = st.text_input("Pessoas envolvidas", value=node.get("pessoas", ""))
                status = st.text_input("Status", value=node.get("status", ""))
                descricao = st.text_area("Descrição", value=node.get("descricao", ""))
                submitted = st.form_submit_button("Salvar")

            if submitted:
                node["categoria"] = cat_ids[cat_idx]
                node["responsavel"] = responsavel
                node["periodo"] = periodo
                node["pessoas"] = pessoas
                node["status"] = status
                node["descricao"] = descricao
                persist("Caixa atualizada!")

        # ---------------- Adicionar seta ----------------
        with tab_new_edge:
            with st.form("new_edge_form"):
                node_ids = list(data["nos"].keys())
                node_labels = [data["nos"][n]["titulo"] for n in node_ids]
                de_idx = st.selectbox("De", range(len(node_ids)), format_func=lambda i: node_labels[i], key="de_sel")
                para_idx = st.selectbox("Para", range(len(node_ids)), format_func=lambda i: node_labels[i], key="para_sel")
                rotulo = st.text_input("Rótulo da seta (opcional)")
                submitted = st.form_submit_button("Adicionar seta")

            if submitted:
                de_id, para_id = node_ids[de_idx], node_ids[para_idx]
                if de_id == para_id:
                    st.error("Escolha duas caixas diferentes.")
                else:
                    new_edge_id = unique_id("e_" + slugify(de_id + "_" + para_id), [e["id"] for e in data["arestas"]])
                    data["arestas"].append({"id": new_edge_id, "de": de_id, "para": para_id, "rotulo": rotulo})
                    persist("Seta adicionada!")

        # ---------------- Adicionar categoria ----------------
        with tab_new_cat:
            with st.form("new_cat_form"):
                cat_nome = st.text_input("Nome da categoria (ex.: nome do responsável ou frente)")
                cat_cor = st.color_picker("Cor", value="#5C8A25")
                submitted = st.form_submit_button("Adicionar categoria")

            if submitted:
                if not cat_nome.strip():
                    st.error("Dê um nome para a categoria antes de adicionar.")
                else:
                    new_id = unique_id(slugify(cat_nome), data["categorias"].keys())
                    data["categorias"][new_id] = {"nome": cat_nome, "cor": cat_cor}
                    persist(f'Categoria "{cat_nome}" adicionada!')

        # ---------------- Excluir ----------------
        with tab_delete:
            st.subheader("Excluir caixa")
            node_ids = list(data["nos"].keys())
            node_labels = [data["nos"][n]["titulo"] for n in node_ids]
            idx = st.selectbox("Caixa a excluir", range(len(node_ids)), format_func=lambda i: node_labels[i], key="del_node_sel")
            nid = node_ids[idx]
            if st.button("Excluir caixa (e as setas ligadas a ela)"):
                del data["nos"][nid]
                data["arestas"] = [e for e in data["arestas"] if e["de"] != nid and e["para"] != nid]
                persist(f'Caixa "{node_labels[idx]}" excluída.')

            st.subheader("Excluir seta")
            if data["arestas"]:
                edge_labels = [f'{data["nos"].get(e["de"], {}).get("titulo", e["de"])} → {data["nos"].get(e["para"], {}).get("titulo", e["para"])}' for e in data["arestas"]]
                eidx = st.selectbox("Seta a excluir", range(len(edge_labels)), format_func=lambda i: edge_labels[i], key="del_edge_sel")
                if st.button("Excluir seta"):
                    removed = data["arestas"].pop(eidx)
                    persist(f'Seta "{edge_labels[eidx]}" excluída.')
            else:
                st.caption("Não há setas para excluir.")
