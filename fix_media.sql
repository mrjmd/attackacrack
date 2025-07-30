-- Check current state
SELECT COUNT(*) as total_with_media
FROM activity 
WHERE media_urls IS NOT NULL 
  AND media_urls::text != '[]';

-- Show a sample of what needs fixing
SELECT id, media_urls 
FROM activity 
WHERE media_urls IS NOT NULL 
  AND media_urls::text != '[]'
  AND media_urls::text NOT LIKE '%"type"%'
LIMIT 5;

-- Update activities where media_urls contains string URLs (not objects)
UPDATE activity
SET media_urls = (
    SELECT jsonb_agg(
        CASE 
            WHEN jsonb_typeof(elem) = 'string' THEN
                jsonb_build_object(
                    'url', elem::text,
                    'type', CASE 
                        WHEN elem::text LIKE '%storage.googleapis.com%' THEN 'image/jpeg'
                        WHEN elem::text LIKE '%.jpg' OR elem::text LIKE '%.jpeg' THEN 'image/jpeg'
                        WHEN elem::text LIKE '%.png' THEN 'image/png'
                        WHEN elem::text LIKE '%.gif' THEN 'image/gif'
                        WHEN elem::text LIKE '%.webp' THEN 'image/webp'
                        ELSE 'application/octet-stream'
                    END
                )
            ELSE elem
        END
    )
    FROM jsonb_array_elements(media_urls) AS elem
)
WHERE media_urls IS NOT NULL 
  AND media_urls::text != '[]'
  AND EXISTS (
    SELECT 1 
    FROM jsonb_array_elements(media_urls) AS elem 
    WHERE jsonb_typeof(elem) = 'string'
  );

-- Show results
SELECT id, media_urls 
FROM activity 
WHERE media_urls IS NOT NULL 
  AND media_urls::text != '[]'
LIMIT 5;