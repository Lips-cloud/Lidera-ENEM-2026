import json
import re
import base64
import unicodedata
import streamlit as st
import streamlit.components.v1 as components
import requests

st.set_page_config(page_title="Lidera Enem — Painel operacional", layout="wide")

DATA_PATH = "data/etapas.json"

STATUS_LABELS = {
    "ok": "Ok",
    "atencao": "Atenção",
    "atraso": "Atrasado / gargalo",
    "naoiniciado": "Não iniciado",
}


# --------------------------------------------------------------------------
# Carregamento e persistência dos dados
# --------------------------------------------------------------------------
def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_to_github(data):
    """Grava o data/etapas.json atualizado direto no repositório do GitHub.
    Cada salvamento vira um commit — histórico automático de mudanças."""
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
    payload = {
        "message": "Atualiza painel Lidera Enem via Streamlit",
        "content": content_b64,
    }
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
# Utilitários para criar novos ids e cores a partir do que a pessoa digita
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


def lighten(hex_color, amount=0.85):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02X}{g:02X}{b:02X}"


# --------------------------------------------------------------------------
# Template visual — a mesma linha do tempo com marcos e post-its
# --------------------------------------------------------------------------
BOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Kalam:wght@400;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{ --status-ok:#3B8B4A; --status-atencao:#B0790F; --status-atraso:#B23B3B; --status-naoiniciado:#8B8E87; --ink:#2B2A24; --ink-soft:#6B6A5F; --board:#EDE6D4; }
  *{box-sizing:border-box;} html,body{margin:0;padding:0;}
  body{font-family:'Inter',sans-serif; color:var(--ink); background:var(--board);}
  .board-scroll{ overflow-x:auto; overflow-y:auto; height:640px; position:relative;
    background-image:radial-gradient(#DFD6BE 1px, transparent 1px); background-size:14px 14px; }
  .board-zoom-wrapper{ position:relative; }
  .board-canvas{ position:relative; height:620px; min-width:2620px; transform-origin:0 0; }
  .zoom-controls{ position:absolute; top:14px; right:14px; display:flex; gap:6px; z-index:20; }
  .zoom-btn{ width:30px; height:30px; border-radius:8px; border:1px solid #DAD2BC; background:#FFFDF6;
    color:var(--ink); font-size:15px; cursor:pointer; }
  .zoom-btn:hover{border-color:#B7AC8C;}
  .zoom-level{ font-size:12px; color:var(--ink-soft); background:#FFFDF6; border:1px solid #DAD2BC;
    border-radius:8px; padding:0 8px; display:flex; align-items:center; min-width:44px; justify-content:center; }
  .spine{ position:absolute; left:0; top:340px; height:6px; width:100%;
    background:repeating-linear-gradient(90deg, #C9BE9E 0 18px, transparent 18px 28px); border-radius:4px; }
  .milestone-group{position:absolute; top:340px;}
  .milestone{ position:absolute; left:0; top:0; transform:translate(-50%,-50%); width:46px; height:46px; border-radius:50%;
    background:#2B2A24; color:#F4EFE2; display:flex; align-items:center; justify-content:center;
    font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:16px; cursor:pointer; z-index:5;
    border:4px solid var(--board); box-shadow:0 0 0 2px #2B2A24; transition:transform .15s ease; }
  .milestone:hover{transform:translate(-50%,-50%) scale(1.08);}
  .milestone.expanded{background:var(--status-ok);}
  .milestone-flag{ position:absolute; left:0; top:-58px; transform:translate(-50%,0); background:#2B2A24; color:#F4EFE2;
    padding:6px 14px; border-radius:6px; font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:13px;
    white-space:nowrap; text-align:center; cursor:pointer; }
  .milestone-flag::after{ content:''; position:absolute; left:50%; bottom:-6px; transform:translateX(-50%);
    border-left:6px solid transparent; border-right:6px solid transparent; border-top:6px solid #2B2A24; }
  .milestone-count{ position:absolute; left:0; top:34px; transform:translate(-50%,0); font-size:11px; color:var(--ink-soft);
    white-space:nowrap; text-align:center; width:100%; }
  .connector{ position:absolute; left:0; top:0; height:2px; background:#B7AC8C; transform-origin:0 50%; opacity:0;
    transition:opacity .25s ease; pointer-events:none; }
  .milestone-group.expanded .connector{opacity:1;}
  .postit{ position:absolute; left:0; top:0; width:150px; transform:translate(-50%,-50%) scale(0.4) rotate(0deg);
    opacity:0; pointer-events:none; transition:transform .28s cubic-bezier(.2,.8,.2,1), opacity .22s ease; z-index:6; }
  .milestone-group.expanded .postit{ opacity:1; pointer-events:auto; }
  .postit-card{ background:#FFFDF6; border-radius:2px; padding:12px 12px 10px; box-shadow:0 3px 8px rgba(0,0,0,0.18);
    cursor:pointer; position:relative; border-top:22px solid var(--pc); }
  .postit-card:hover{box-shadow:0 5px 14px rgba(0,0,0,0.24);}
  .postit-tape{ position:absolute; top:-10px; left:50%; transform:translateX(-50%) rotate(-3deg); width:56px; height:18px;
    background:rgba(255,255,255,0.55); border:1px solid rgba(255,255,255,0.7); }
  .postit-name{ font-family:'Kalam',cursive; font-weight:700; font-size:14.5px; color:var(--ink); line-height:1.25; }
  .postit-resp{font-size:11px; color:var(--ink-soft); margin-top:6px;}
  .postit-status-dot{ position:absolute; top:-14px; right:8px; width:11px; height:11px; border-radius:50%; border:2px solid #FFFDF6; }
  #drawer{ position:fixed; top:0; right:0; height:100vh; width:340px; background:#FFFDF6; border-left:1px solid #DAD2BC;
    transform:translateX(100%); transition:transform .28s cubic-bezier(.2,.8,.2,1); z-index:500; padding:22px; overflow-y:auto;
    font-family:'Inter',sans-serif; color:var(--ink); }
  #drawer.open{transform:translateX(0);}
  #drawer-overlay{ position:fixed; inset:0; background:rgba(30,28,20,0.25); opacity:0; pointer-events:none;
    transition:opacity .28s ease; z-index:400; }
  #drawer-overlay.open{opacity:1; pointer-events:auto;}
  .drawer-close{background:none; border:none; color:var(--ink-soft); font-size:18px; cursor:pointer; position:absolute; top:18px; right:18px;}
  .drawer-area{ display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:600; text-transform:uppercase;
    letter-spacing:.05em; padding:4px 10px; border-radius:20px; margin-bottom:14px; }
  .drawer-name{font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:18px; margin:0 0 16px; padding-right:24px;}
  .drawer-field{margin-bottom:14px;}
  .drawer-field .dl{font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--ink-soft); margin-bottom:4px;}
  .drawer-field .dv{font-size:14px; color:var(--ink); line-height:1.5;}
  .drawer-status{display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:600; padding:4px 10px; border-radius:20px;}
  .drawer-status .dot{width:6px; height:6px; border-radius:50%;}
  .scroll-hint{ position:absolute; bottom:14px; left:50%; transform:translateX(-50%); font-size:12px; color:var(--ink-soft);
    background:#FFFDF6; border:1px solid #DAD2BC; padding:5px 12px; border-radius:20px; z-index:50; }
</style>
</head>
<body>
<div class="board-scroll">
  <div class="zoom-controls">
    <button class="zoom-btn" id="zoom-out">&minus;</button>
    <div class="zoom-level" id="zoom-level">100%</div>
    <button class="zoom-btn" id="zoom-in">+</button>
    <button class="zoom-btn" id="zoom-reset" style="width:auto; padding:0 8px; font-size:11px;">reset</button>
  </div>
  <div class="board-zoom-wrapper" id="board-zoom-wrapper">
    <div class="board-canvas" id="board-canvas"></div>
  </div>
  <div class="scroll-hint">&larr; role na horizontal &rarr;</div>
</div>
<div id="drawer-overlay"></div>
<div id="drawer">
  <button class="drawer-close" id="drawer-close">&#10005;</button>
  <div id="drawer-body"></div>
</div>
<script>
  const AREAS = __AREAS__;
  const ETAPAS = __ETAPAS__;
  const MARCOS = __MARCOS__;
  const STATUS_LABELS = {ok:'Ok', atencao:'Atenção', atraso:'Atrasado / gargalo', naoiniciado:'Não iniciado'};
  function statusColor(s){ return {ok:'var(--status-ok)', atencao:'var(--status-atencao)', atraso:'var(--status-atraso)', naoiniciado:'var(--status-naoiniciado)'}[s]; }

  const SPACING = 640, START_X = 300;

  function buildBoard(){
    const canvas = document.getElementById('board-canvas');
    const totalWidth = START_X + (MARCOS.length-1)*SPACING + 400;
    const totalHeight = 620;
    canvas.style.minWidth = totalWidth + 'px';
    let html = '<div class="spine"></div>';

    MARCOS.forEach((marco, mi)=>{
      const mx = START_X + mi*SPACING;
      const k = marco.etapas.length;
      let inner = `
        <div class="milestone-flag" onclick="toggleMarco('${marco.id}')">${marco.nome}</div>
        <div class="milestone" onclick="toggleMarco('${marco.id}')">${mi+1}</div>
        <div class="milestone-count" onclick="toggleMarco('${marco.id}')">${k} etapa${k>1?'s':''} &middot; clique para abrir</div>`;

      marco.etapas.forEach((etapaId, i)=>{
        const side = i % 2 === 0 ? -1 : 1;
        const rank = Math.floor(i/2);
        const dx = (i - (k-1)/2) * 125;
        const dy = side * (130 + rank*12);
        const len = Math.sqrt(dx*dx + dy*dy);
        const ang = Math.atan2(dy, dx) * 180 / Math.PI;
        const etapa = ETAPAS[etapaId];
        const area = AREAS[etapa.area];
        inner += `<div class="connector" style="width:${len}px; transform:rotate(${ang}deg);"></div>`;
        inner += `
          <div class="postit" style="left:${dx}px; top:${dy}px;">
            <div class="postit-card" style="--pc:${area.cor}" onclick="openDrawer('${etapaId}')">
              <span class="postit-status-dot" style="background:${statusColor(etapa.status)}"></span>
              <div class="postit-tape"></div>
              <div class="postit-name">${etapa.nome}</div>
              <div class="postit-resp">${etapa.responsavel}</div>
            </div>
          </div>`;
      });
      html += `<div class="milestone-group" id="mg-${marco.id}" style="left:${mx}px;">${inner}</div>`;
    });
    canvas.innerHTML = html;
    toggleMarco(MARCOS[0].id, true);
    setupZoom(totalWidth, totalHeight);
  }

  function setupZoom(baseWidth, baseHeight){
    const canvas = document.getElementById('board-canvas');
    const wrapper = document.getElementById('board-zoom-wrapper');
    const levelLabel = document.getElementById('zoom-level');
    let scale = 1;
    const MIN = 0.5, MAX = 2, STEP = 0.15;

    function apply(){
      canvas.style.transform = `scale(${scale})`;
      wrapper.style.width = (baseWidth*scale) + 'px';
      wrapper.style.height = (baseHeight*scale) + 'px';
      levelLabel.textContent = Math.round(scale*100) + '%';
    }
    apply();

    document.getElementById('zoom-in').addEventListener('click', ()=>{ scale = Math.min(MAX, +(scale+STEP).toFixed(2)); apply(); });
    document.getElementById('zoom-out').addEventListener('click', ()=>{ scale = Math.max(MIN, +(scale-STEP).toFixed(2)); apply(); });
    document.getElementById('zoom-reset').addEventListener('click', ()=>{ scale = 1; apply(); });

    document.getElementById('board-canvas').closest('.board-scroll').addEventListener('wheel', function(e){
      if(!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      scale = e.deltaY < 0 ? Math.min(MAX, +(scale+0.08).toFixed(2)) : Math.max(MIN, +(scale-0.08).toFixed(2));
      apply();
    }, { passive:false });
  }

  function toggleMarco(id, forceOpen){
    const group = document.getElementById('mg-'+id);
    const isOpen = group.classList.contains('expanded');
    if(forceOpen && isOpen) return;
    group.classList.toggle('expanded', forceOpen ? true : !isOpen);
    group.querySelector('.milestone').classList.toggle('expanded', group.classList.contains('expanded'));
  }

  function openDrawer(etapaId){
    const e = ETAPAS[etapaId];
    const area = AREAS[e.area];
    document.getElementById('drawer-body').innerHTML = `
      <span class="drawer-area" style="background:${area.bg}; color:${area.cor}">${area.nome}</span>
      <p class="drawer-name">${e.nome}</p>
      <div class="drawer-field"><div class="dl">Status</div>
        <span class="drawer-status" style="background:${statusColor(e.status)}22; color:${statusColor(e.status)}">
          <span class="dot" style="background:${statusColor(e.status)}"></span>${STATUS_LABELS[e.status]}
        </span>
      </div>
      <div class="drawer-field"><div class="dl">Responsável</div><div class="dv">${e.responsavel}</div></div>
      <div class="drawer-field"><div class="dl">Prazo</div><div class="dv">${e.prazo || 'A definir'}</div></div>
      <div class="drawer-field"><div class="dl">Descrição</div><div class="dv">${e.descricao}</div></div>
      ${e.gargalo ? `<div class="drawer-field"><div class="dl">Gargalo / observação</div><div class="dv">${e.gargalo}</div></div>` : ''}
    `;
    document.getElementById('drawer').classList.add('open');
    document.getElementById('drawer-overlay').classList.add('open');
  }
  function closeDrawer(){
    document.getElementById('drawer').classList.remove('open');
    document.getElementById('drawer-overlay').classList.remove('open');
  }
  document.getElementById('drawer-close').addEventListener('click', closeDrawer);
  document.getElementById('drawer-overlay').addEventListener('click', closeDrawer);
  buildBoard();
</script>
</body>
</html>
"""


def render_board(data):
    html = (
        BOARD_TEMPLATE
        .replace("__AREAS__", json.dumps(data["areas"], ensure_ascii=False))
        .replace("__ETAPAS__", json.dumps(data["etapas"], ensure_ascii=False))
        .replace("__MARCOS__", json.dumps(data["marcos"], ensure_ascii=False))
    )
    components.html(html, height=680, scrolling=False)


# --------------------------------------------------------------------------
# Layout da página
# --------------------------------------------------------------------------
st.title("Lidera Enem — painel operacional")
st.caption("Clique em um marco para abrir as etapas dentro dele, e em cada post-it para ver os detalhes.")

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

        def persist(success_msg):
            st.session_state.data = data
            ok, err = save_to_github(data)
            if ok:
                st.success(success_msg + " O painel público atualiza em cerca de 1 minuto.")
                st.rerun()
            else:
                st.error(f"Não consegui salvar no GitHub: {err}")

        tab_edit, tab_new_etapa, tab_new_marco, tab_new_area, tab_delete = st.tabs(
            ["Editar", "+ Etapa", "+ Marco", "+ Equipe", "Excluir"]
        )

        # ---------------- Editar etapa existente ----------------
        with tab_edit:
            etapa_ids = list(data["etapas"].keys())
            labels = [data["etapas"][eid]["nome"] for eid in etapa_ids]
            idx = st.selectbox("Etapa", range(len(etapa_ids)), format_func=lambda i: labels[i], key="edit_sel")
            eid = etapa_ids[idx]
            etapa = data["etapas"][eid]

            with st.form("edit_form"):
                area_ids = list(data["areas"].keys())
                area_labels = [data["areas"][a]["nome"] for a in area_ids]
                area_idx = st.selectbox(
                    "Equipe / área", range(len(area_ids)), format_func=lambda i: area_labels[i],
                    index=area_ids.index(etapa["area"]),
                )
                responsavel = st.text_input("Responsável", value=etapa["responsavel"])
                prazo = st.text_input("Prazo", value=etapa.get("prazo", ""))
                status = st.selectbox(
                    "Status", list(STATUS_LABELS.keys()), format_func=lambda s: STATUS_LABELS[s],
                    index=list(STATUS_LABELS.keys()).index(etapa["status"]),
                )
                descricao = st.text_area("Descrição", value=etapa["descricao"])
                gargalo = st.text_area("Gargalo / observação", value=etapa.get("gargalo", ""))
                submitted = st.form_submit_button("Salvar")

            if submitted:
                etapa["area"] = area_ids[area_idx]
                etapa["responsavel"] = responsavel
                etapa["prazo"] = prazo
                etapa["status"] = status
                etapa["descricao"] = descricao
                etapa["gargalo"] = gargalo
                persist("Etapa atualizada!")

        # ---------------- Adicionar nova etapa ----------------
        with tab_new_etapa:
            with st.form("new_etapa_form"):
                nome = st.text_input("Nome da etapa")
                area_ids = list(data["areas"].keys())
                area_labels = [data["areas"][a]["nome"] for a in area_ids]
                area_idx = st.selectbox("Equipe / área", range(len(area_ids)), format_func=lambda i: area_labels[i])
                marco_ids = [m["id"] for m in data["marcos"]]
                marco_labels = [m["nome"] for m in data["marcos"]]
                marco_idx = st.selectbox("Marco onde ela entra", range(len(marco_ids)), format_func=lambda i: marco_labels[i])
                responsavel = st.text_input("Responsável", value="A definir")
                prazo = st.text_input("Prazo", value="A definir")
                status = st.selectbox("Status", list(STATUS_LABELS.keys()), format_func=lambda s: STATUS_LABELS[s])
                descricao = st.text_area("Descrição")
                gargalo = st.text_area("Gargalo / observação (opcional)")
                submitted = st.form_submit_button("Adicionar etapa")

            if submitted:
                if not nome.strip():
                    st.error("Dê um nome para a etapa antes de adicionar.")
                else:
                    new_id = unique_id(slugify(nome), data["etapas"].keys())
                    data["etapas"][new_id] = {
                        "nome": nome, "area": area_ids[area_idx], "responsavel": responsavel,
                        "status": status, "prazo": prazo, "descricao": descricao, "gargalo": gargalo,
                    }
                    data["marcos"][marco_idx]["etapas"].append(new_id)
                    persist(f'Etapa "{nome}" adicionada!')

        # ---------------- Adicionar novo marco ----------------
        with tab_new_marco:
            with st.form("new_marco_form"):
                marco_nome = st.text_input("Nome do marco (ex.: Produção de kits)")
                submitted = st.form_submit_button("Adicionar marco")

            if submitted:
                if not marco_nome.strip():
                    st.error("Dê um nome para o marco antes de adicionar.")
                else:
                    existing = [m["id"] for m in data["marcos"]]
                    new_id = unique_id("m" + slugify(marco_nome), existing)
                    data["marcos"].append({"id": new_id, "nome": marco_nome, "etapas": []})
                    persist(f'Marco "{marco_nome}" adicionado! Agora vá em "+ Etapa" para colocar etapas dentro dele.')

        # ---------------- Adicionar nova equipe / área ----------------
        with tab_new_area:
            with st.form("new_area_form"):
                area_nome = st.text_input("Nome da equipe / área (ex.: Logística)")
                area_cor = st.color_picker("Cor da equipe", value="#5C8A25")
                submitted = st.form_submit_button("Adicionar equipe")

            if submitted:
                if not area_nome.strip():
                    st.error("Dê um nome para a equipe antes de adicionar.")
                else:
                    new_id = unique_id(slugify(area_nome), data["areas"].keys())
                    data["areas"][new_id] = {"nome": area_nome, "cor": area_cor, "bg": lighten(area_cor)}
                    persist(f'Equipe "{area_nome}" adicionada! Já aparece disponível para escolher nas etapas.')

        # ---------------- Excluir etapa ----------------
        with tab_delete:
            etapa_ids = list(data["etapas"].keys())
            labels = [data["etapas"][eid]["nome"] for eid in etapa_ids]
            idx = st.selectbox("Etapa a excluir", range(len(etapa_ids)), format_func=lambda i: labels[i], key="del_sel")
            eid = etapa_ids[idx]
            st.warning(f'Isso remove "{labels[idx]}" do painel. Não dá para desfazer por aqui (mas fica no histórico do GitHub).')
            if st.button("Excluir etapa definitivamente"):
                del data["etapas"][eid]
                for m in data["marcos"]:
                    if eid in m["etapas"]:
                        m["etapas"].remove(eid)
                persist(f'Etapa "{labels[idx]}" excluída.')
