# MapaConcursosKML

Este projeto realiza web scraping no site PCI Concursos para identificar concursos públicos com cargos de interesse (ex: Auditor Fiscal, Contador, etc) e gera um arquivo `.kml` com geolocalização para visualização no Google Earth.

## ✅ O que ele faz:
- Busca concursos no site https://www.pciconcursos.com.br/concursos/
- Verifica se há cargos de interesse
- Extrai data final de inscrição
- Gera arquivo `ConcursosAtivosDDMMAAAA.kml` com pins coloridos por status:
  - 🟢 Verde: mais de 15 dias restantes
  - 🟡 Amarelo: menos de 15 dias
  - 🔴 Vermelho: inscrição encerrada

## 🚀 Executando localmente

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/MapaConcursosKML.git
cd MapaConcursosKML
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute o script:
```bash
python script.py
```

## ☁️ Execução automática (Railway + Cron Job)

1. Suba este projeto no GitHub
2. Vá em [Railway.app](https://railway.app)
3. Crie um novo projeto e conecte ao seu GitHub
4. Crie um Cron Job:
   - Schedule: `0 6 * * *` (roda todo dia às 6h da manhã)
   - Command: `python script.py`
5. Pronto! O `.kml` será gerado automaticamente todos os dias.

## 🔐 API Key
Você deve possuir uma chave da API do OpenCage. Adicione no código em:
```python
OPENCAGE_API_KEY = "SUA_CHAVE_AQUI"
```

Ou salve como variável de ambiente:
```bash
export OPENCAGE_API_KEY="SUA_CHAVE"
```

## 📂 Arquivos gerados
- `ConcursosAtivosDDMMAAAA.kml`: Mapa com os concursos mais recentes

