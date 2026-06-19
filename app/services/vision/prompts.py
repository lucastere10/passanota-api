EXTRACTION_PROMPT = """Analise esta imagem de nota fiscal ou cupom fiscal brasileiro.
Extraia os dados e retorne APENAS um JSON válido, sem markdown, no formato:

{
  "fornecedor": "nome do estabelecimento",
  "data": "YYYY-MM-DD",
  "itens": [
    {
      "descricao": "nome do produto",
      "valor": 12.99,
      "quantidade": 1
    }
  ],
  "total": 12.99
}

Regras:
- "fornecedor" é o nome da loja/mercado
- "data" no formato ISO YYYY-MM-DD; use null se não legível
- "itens" lista cada produto com "descricao" e "valor" (preço total da linha)
- "quantidade" é opcional
- "total" é o total da nota; use null se não legível
- Valores numéricos como número, não string
- Se não conseguir ler itens, retorne "itens": []
"""
