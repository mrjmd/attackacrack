#!/usr/bin/env python3
"""
Generate SQL to fix media_urls format in existing activities.
Since we can't determine the actual media type from URLs alone,
we'll assume Google Storage URLs are images (which they typically are from OpenPhone).
"""

print("""
-- SQL to fix existing media URLs in the database
-- This assumes URLs from storage.googleapis.com are images

-- First, let's see what we're dealing with
SELECT id, media_urls 
FROM activity 
WHERE media_urls IS NOT NULL 
  AND media_urls::text != '[]'
  AND media_urls::text NOT LIKE '%"type"%'
LIMIT 10;

-- Update activities where media_urls contains string URLs (not objects)
-- This converts ["url1", "url2"] to [{"url": "url1", "type": "image/jpeg"}, {"url": "url2", "type": "image/jpeg"}]
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

-- Verify the update worked
SELECT id, media_urls 
FROM activity 
WHERE media_urls IS NOT NULL 
  AND media_urls::text != '[]'
LIMIT 10;
""")