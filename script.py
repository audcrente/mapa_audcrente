from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from datetime import date, datetime
import pandas as pd
import requests
import re
import unidecode
import simplekml
from opencage.geocoder import OpenCageGeocode
from collections import defaultdict

def normalize_text(texto):
    return unidecode.unidecode(texto.lower().replace("-", " ")).strip()

def limpar_nome_cidade(texto):
    texto = normalize_text(texto)
    texto = re.sub(r"^(prefeitura|camara|tribunal|sefaz|tce|tj|cge|procuradoria|ministerio publico|estado|governo)\s+de\s+", "", texto)
    texto = re.sub(r"[^a-zà-ÿ\s]", "", texto, flags=re.IGNORECASE)
    return texto.strip().title()

cargos_interesse = [
    "auditor fiscal tributario", "auditor fiscal", "contador", "fiscal tributario", "auditor", "controlador", "controlador interno", "fazendario", "tecnico fazendario", 
    "assistente administrativo", "agente administrativo", "fiscal de rendas", "fiscal de tributos", "controlador externo",
    "auditor fiscal de tributos estaduais", "auditor fiscal de tributos municipais", "tributario", "tributos", "rendas",
    "auditor de rendas", "analista tributario", "agente fiscal de rendas", "tecnico em contabilidade", "contabilidade"
]

def contem_cargo_interesse(texto):
    texto = normalize_text(texto)
    palavras_texto = set(texto.split())
    for cargo in cargos_interesse:
        palavras_cargo = normalize_text(cargo).split()
        if all(
            any(
                p in palavras_texto or
                p + "s" in palavras_texto or
                p + "es" in palavras_texto or
                p.rstrip("e") + "is" in palavras_texto
                for p in [palavra]
            )
            for palavra in palavras_cargo
        ):
            return True
    return False

def extrair_cargos_detalhados(link):
    try:
        r = requests.get(link, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            texto = soup.get_text(separator=" ", strip=True)

            # Padrão 1: datas no formato dd/mm/aaaa
            datas_padrao = re.findall(r'(\d{1,2}/\d{1,2}/\d{4})', texto)

            # Padrão 2: datas com mês por extenso
            meses = {
                "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03", "abril": "04",
                "maio": "05", "junho": "06", "julho": "07", "agosto": "08", "setembro": "09",
                "outubro": "10", "novembro": "11", "dezembro": "12"
            }

            datas_extenso = []
            for match in re.findall(r'(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})', texto, re.IGNORECASE):
                dia, mes_ext, ano = match
                mes_num = meses.get(mes_ext.lower())
                if mes_num:
                    datas_extenso.append(f"{int(dia):02d}/{mes_num}/{ano}")

            todas_datas = datas_padrao + datas_extenso
            inscricao_ate = "-"
            for data in todas_datas:
                try:
                    data_convertida = datetime.strptime(data, "%d/%m/%Y")
                    if datetime.today() <= data_convertida <= datetime.today().replace(year=datetime.today().year + 1):
                        inscricao_ate = data
                        break
                except:
                    continue

            return texto, inscricao_ate
    except Exception:
        pass
    return "", "-"

def fetch_detalhado_if_promissor(nome, link):
    texto_titulo = normalize_text(nome)
    palavras_gatilho_cargo = [
        "fiscal", "contador", "contabil", "controlador", "auditor", "auditor fiscal", 
        "tribut", "receita", "tesouro", "orcamento", "financeiro", "patrimonial", "renda", "fazendario",
        "analista", "planejamento", "gestao publica", "controle interno", "prestacao de contas", "prefeitura", "camara"
    ]
    palavras_gatilho_orgao = [
        "prefeitura", "municipio", "estado", "governo", "camara", "assembleia", "tribunal", 
        "justica", "ministerio publico", "promotoria", "procuradoria", 
        "secretaria de fazenda", "fazenda", "sefaz", "tce", "tcm", "receita", 
        "controladoria", "cge", "cgu", "tcu", "iss", "conselho regional"
    ]
    if any(p in texto_titulo for p in palavras_gatilho_cargo + palavras_gatilho_orgao):
        descricao, inscricao_ate = extrair_cargos_detalhados(link)
        if contem_cargo_interesse(descricao):
            return nome, descricao[:5000], link, inscricao_ate
    return None

def separar_palavras_coladas(texto):
    if " " in texto:
        return texto
    return ' '.join(re.findall(r'[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõç]*', texto.title()))

def extract_state_concursos(soup):
    concursos = []
    blocos = soup.find_all("div", class_="ca")
    print(f"🔍 Total de blocos de concursos na página: {len(blocos)}")
    pool = ThreadPoolExecutor(max_workers=10)
    futures = []
    for i, bloco in enumerate(blocos, start=1):
        nome = bloco.find("a").text.strip()
        print(f"📌 {i}/{len(blocos)}: {nome}")
        link = bloco.find("a")["href"]
        uf_tag = bloco.find_previous("div", class_="uf")
        if uf_tag:
            estado = uf_tag.text.strip()
            uf = estado[-2:]
        else:
            estado = "-"
            uf = "-"
            print(f"⚠️ Estado não encontrado para concurso: {nome}")
        vagas = ''.join(re.findall(r'(\d+)\s+vaga', str(bloco)))
        nivel = '/'.join(re.findall(r'Superior|Médio|Fundamental', str(bloco)))
        salario = ''.join(re.findall(r'R\$ *\d{1,3}(?:\.\d{3})*,\d{2}', str(bloco)))
        inscricao = ''.join(re.findall(r'\d{2}/\d{2}/\d{4}', str(bloco)))
        cargos_resumo = bloco.find(class_='cd').get_text(separator=" ").strip() if bloco.find(class_='cd') else "-"
        texto_completo_primario = f"{nome} {cargos_resumo}"
        if contem_cargo_interesse(texto_completo_primario):
            print("✅ Cargo de interesse encontrado no título ou resumo.")
            concursos.append([nome, vagas or "-", cargos_resumo, nivel or "-", salario or "-", inscricao or "-", link, uf, estado])
        else:
            futures.append(pool.submit(fetch_detalhado_if_promissor, nome, link))
    for future in as_completed(futures):
        result = future.result()
        if result:
            nome, descricao_detalhada, link, inscricao_ate = result
            concursos.append([nome, "-", descricao_detalhada, "-", "-", inscricao_ate or "-", link, "-", "-"])
            print(f"✅ Cargo encontrado no edital completo: {nome}")
        else:
            print("❌ Nenhum cargo de interesse.")
    return concursos

if __name__ == '__main__':
    url = "https://www.pciconcursos.com.br/concursos/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    hoje = date.today().strftime("%d%m%Y")

    concursos_desejados = extract_state_concursos(soup)
    df = pd.DataFrame(concursos_desejados, columns=[
        "Concurso", "Vagas", "Cargos", "Nível", "Salário Até", "Inscrição Até", "Link", "UF", "Estado"
    ])
    df = df.replace(r'^\s*$', '-', regex=True)

    print("🌍 Gerando arquivo KML para o Google Earth...")
    kml = simplekml.Kml()
    OPENCAGE_API_KEY = "9c733e494d164c62be60589f6c7a38ac"
    geocoder = OpenCageGeocode(OPENCAGE_API_KEY)
    coordenadas_cache = {}

    print("📦 Agrupando concursos por cidade...")
    concursos_por_local = defaultdict(list)
    for _, row in df.iterrows():
        match = re.search(r"(?i)(prefeitura|camara|tce|tj|sefaz|tribunal|cge|fhemig|procuradoria|ministerio publico)[^-\n]*", row['Concurso'])
        nome_base = match.group(0).strip() if match else row['Concurso'].split("-")[0].strip()
        cidade_limpa = limpar_nome_cidade(nome_base)
        cidade_formatada = separar_palavras_coladas(cidade_limpa)
        chave_local = f"{cidade_formatada}, {row['Estado']}, Brasil"
        concursos_por_local[chave_local].append(row)

    print("📍 Gerando pins únicos por cidade...")
    for local, concursos in concursos_por_local.items():
        if local in coordenadas_cache:
            longitude, latitude = coordenadas_cache[local]
        else:
            results = geocoder.geocode(local, no_annotations=1, language='pt')
            if results:
                location = results[0]['geometry']
                latitude = location['lat']
                longitude = location['lng']
                coordenadas_cache[local] = (longitude, latitude)
            else:
                print(f"❌ Local não encontrado: {local}")
                continue

        descricao_balao = ""
        dias_restantes_pin = -1

        for row in concursos:
            try:
                if row['Inscrição Até'] and row['Inscrição Até'] != "-":
                    data_limite = datetime.strptime(row['Inscrição Até'], "%d/%m/%Y")
                    dias_restantes = (data_limite - datetime.today()).days
                else:
                    dias_restantes = -1
            except:
                dias_restantes = -1

            if dias_restantes_pin == -1 or (dias_restantes >= 0 and dias_restantes < dias_restantes_pin):
                dias_restantes_pin = dias_restantes

            cargos_texto = row['Cargos']
            cargos_identificados = []
            for cargo in cargos_interesse:
                if normalize_text(cargo) in normalize_text(cargos_texto):
                    cargos_identificados.append(cargo.title())

            cargos_formatado = ", ".join(cargos_identificados) if cargos_identificados else "Não identificado"

            descricao_balao += (
                f"<div style='font-family:sans-serif;font-size:14px;'>"
                f"<h3 style='margin-bottom:4px;'>📍 {row['Concurso']}</h3>"
                f"<p><b>🗂️ Cargos de interesse:</b> {cargos_formatado}</p>"
                f"<p><b>📝 Inscrição até:</b> {row['Inscrição Até']} "
                f"({dias_restantes if dias_restantes >= 0 else 'Encerrado'} dia(s) restantes)</p>"
                f"<p><a href='{row['Link']}' target='_blank'>🔗 Acessar edital</a></p>"
                f"</div><hr/>"
            )

        # Definição do ícone conforme dias restantes
        if dias_restantes_pin > 15:
            icon_url = "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
        elif 0 <= dias_restantes_pin <= 15:
            icon_url = "http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png"
        else:
            icon_url = "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"

        # Criação do ponto com name vazio (não aparece sobre o pin no mapa)
        pnt = kml.newpoint(
            name="",  # Oculta nome flutuante
            description=descricao_balao,
            coords=[(longitude, latitude)]
        )
        pnt.style.iconstyle.icon.href = icon_url
        pnt.style.iconstyle.scale = 1.3
        pnt.style.labelstyle.scale = 0

        print(f"📌 Pin único criado para {local.replace(', -, Brasil', '').replace(', Brasil', '')}")

    arquivo = f"ConcursosAtivos{hoje}.kml"
    if os.path.exists(arquivo):
        print(f"✅ Arquivo encontrado: {arquivo}")
        sys.exit(0)
    else:
        print(f"❌ Erro: Arquivo {arquivo} não encontrado.")
        sys.exit(1)