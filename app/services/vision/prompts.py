EXTRACTION_PROMPT = """Analise esta imagem de nota fiscal ou cupom fiscal brasileiro.
Extraia os dados e retorne APENAS um JSON válido, sem markdown, no formato:

{
  "fornecedor": "NOME DA LOJA",
  "cnpj": "12345678000199",
  "data": "YYYY-MM-DD",
  "itens": [
    {
      "descricao": "nome do produto",
      "valor": 12.99,
      "quantidade": 1,
      "categoria": "alimentacao"
    }
  ],
  "total": 12.99,
  "confianca": 0.85
}

Regras:
- "fornecedor" é o nome comercial da loja/mercado, como impresso no cupom
- "cnpj" é o CNPJ do estabelecimento (apenas 14 dígitos, sem pontuação); use null se não legível
- "data" no formato ISO YYYY-MM-DD; use null se não legível
- "itens" lista cada produto com "descricao" e "valor" (preço total da linha)
- "quantidade" é opcional
- "categoria" é obrigatória em cada item; use EXATAMENTE um destes slugs:
  alimentacao, bebidas, higiene, limpeza, vestuario, outros
  - alimentacao: comida, arroz, feijão, pão, carne, laticínios, etc.
  - bebidas: refrigerantes, sucos, cerveja, água, vinho, etc.
  - higiene: sabonete, shampoo, pasta de dente, desodorante, etc.
  - limpeza: detergente, sabão, desinfetante, etc.
  - vestuario: roupas, calçados, acessórios de vestuário
  - outros: quando não se encaixa nas categorias acima ou estiver incerto
- "total" é o total da nota; use null se não legível
- "confianca" é um número entre 0.0 e 1.0 indicando o quão confiante você está na extração (legibilidade da imagem, completude dos campos e consistência entre soma dos itens e total)
- Valores numéricos como número, não string
- Se não conseguir ler itens, retorne "itens": []
"""
