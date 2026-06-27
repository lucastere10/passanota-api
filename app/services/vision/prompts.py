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
  "total": 12.99,
  "confianca": 0.85
}

Regras:
- "fornecedor" é o nome da loja/mercado
- "data" no formato ISO YYYY-MM-DD; use null se não legível
- "itens" lista cada produto com "descricao" e "valor" (preço total da linha)
- "quantidade" é opcional
- "total" é o total da nota; use null se não legível
- "confianca" é um número entre 0.0 e 1.0 indicando o quão confiante você está na extração (legibilidade da imagem, completude dos campos e consistência entre soma dos itens e total)
- Valores numéricos como número, não string
- Se não conseguir ler itens, retorne "itens": []
"""
