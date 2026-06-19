-- Funções SQL para normalização e categorização pós-extração IA.
-- Para uso manual no SQL Editor do Supabase (aceita múltiplos comandos).
-- Via Alembic, cada função é executada em um statement separado (asyncpg).

CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE OR REPLACE FUNCTION assign_category_id(
    p_description text,
    p_embedding vector DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_desc text;
    v_category_id uuid;
BEGIN
    v_desc := upper(trim(coalesce(p_description, '')));

    IF v_desc = '' THEN
        SELECT id INTO v_category_id FROM categories WHERE slug = 'outros' LIMIT 1;
        RETURN v_category_id;
    END IF;

    SELECT c.id INTO v_category_id
    FROM categories c
    WHERE c.keywords IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM unnest(c.keywords) AS kw
          WHERE v_desc ILIKE '%' || kw || '%'
      )
    ORDER BY length(
        (SELECT kw FROM unnest(c.keywords) AS kw
         WHERE v_desc ILIKE '%' || kw || '%'
         ORDER BY length(kw) DESC LIMIT 1)
    ) DESC
    LIMIT 1;

    IF v_category_id IS NOT NULL THEN
        RETURN v_category_id;
    END IF;

    IF p_embedding IS NOT NULL THEN
        SELECT c.id INTO v_category_id
        FROM categories c
        WHERE c.embedding IS NOT NULL
        ORDER BY c.embedding <=> p_embedding
        LIMIT 1;

        IF v_category_id IS NOT NULL THEN
            RETURN v_category_id;
        END IF;
    END IF;

    SELECT id INTO v_category_id FROM categories WHERE slug = 'outros' LIMIT 1;
    RETURN v_category_id;
END;
$$;

CREATE OR REPLACE FUNCTION normalize_invoice_items(p_invoice_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_total numeric(15, 2);
BEGIN
    UPDATE invoice_items
    SET description = upper(trim(description))
    WHERE invoice_id = p_invoice_id;

    UPDATE invoice_items ii
    SET category_id = assign_category_id(ii.description, ii.embedding)
    WHERE ii.invoice_id = p_invoice_id;

    SELECT coalesce(sum(total_price), 0) INTO v_total
    FROM invoice_items
    WHERE invoice_id = p_invoice_id;

    UPDATE invoices
    SET total_amount = CASE
        WHEN total_amount IS NULL OR total_amount = 0 THEN v_total
        ELSE total_amount
    END,
    updated_at = now()
    WHERE id = p_invoice_id;
END;
$$;
