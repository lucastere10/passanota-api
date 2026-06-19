-- Bucket privado para fotos de notas fiscais.
-- Execute no SQL Editor do Supabase.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'invoice-photos',
    'invoice-photos',
    false,
    10485760,
    ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO NOTHING;
