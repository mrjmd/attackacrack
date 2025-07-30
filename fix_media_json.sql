-- Update activities where media_urls contains string URLs (not objects)
UPDATE activity
SET media_urls = (
    SELECT json_agg(
        CASE 
            WHEN json_typeof(elem) = 'string' THEN
                json_build_object(
                    'url', elem::text,
                    'type', CASE 
                        WHEN elem::text LIKE '%storage.googleapis.com%' THEN 'image/jpeg'
                        WHEN elem::text LIKE '%.jpg' OR elem::text LIKE '%.jpeg' THEN 'image/jpeg'
                        WHEN elem::text LIKE '%.png' THEN 'image/png'
                        WHEN elem::text LIKE '%.gif' THEN 'image/gif'
                        WHEN elem::text LIKE '%.webp' THEN 'image/webp'
                        ELSE 'application/octet-stream'
                    END
                )::json
            ELSE elem
        END
    )
    FROM json_array_elements(media_urls) AS elem
)
WHERE media_urls IS NOT NULL 
  AND media_urls::text != '[]'
  AND EXISTS (
    SELECT 1 
    FROM json_array_elements(media_urls) AS elem 
    WHERE json_typeof(elem) = 'string'
  );

-- Show the updated results
SELECT id, media_urls 
FROM activity 
WHERE id IN (14040, 14041);