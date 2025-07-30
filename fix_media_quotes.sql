-- Fix the extra quotes issue
UPDATE activity
SET media_urls = (
    SELECT json_agg(
        json_build_object(
            'url', trim(both '"' from (elem->>'url')),
            'type', elem->>'type'
        )::json
    )
    FROM json_array_elements(media_urls) AS elem
)
WHERE media_urls IS NOT NULL 
  AND media_urls::text LIKE '%\\"%';

-- Show the fixed results
SELECT id, media_urls 
FROM activity 
WHERE id IN (14040, 14041);