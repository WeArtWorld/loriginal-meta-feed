# L'Original: Meta catalog feed

This repo builds the product feed for the Meta catalog "L'Original — Œuvres" (`598914184189673`).

Every night at 07:17 UTC, a GitHub Action reads the public artwork API on loriginal.org, writes four CSV files to `flux/`, and commits them. Meta and Pinterest fetch these files every day.

| File | Meta feed | What it holds |
|---|---|---|
| `flux/catalogue-fr.csv` | `Flux Merchant Center FR` (primary) | One row per artwork still for sale, in French |
| `flux/catalogue-en.csv` | `Traductions EN (en_XX)` (language override) | English title, description and link for the same ids |
| `flux/catalogue-pinterest-fr.csv` | Pinterest catalog "L'Original - Oeuvres", French source | Same rows as the French file, minus `exclusions-pinterest.txt` |
| `flux/catalogue-pinterest-en.csv` | Pinterest catalog, English source | Full rows (price, images, labels) with the English title, description and link |

## Pinterest exclusions

Pinterest rejects a merchant account if its catalog holds products against its merchant guidelines, and artistic nudity counts. `exclusions-pinterest.txt` lists the ids to keep out of the two Pinterest files, one per line. Text after `#` is a comment. The Meta files are not affected.

## The artwork API pages its results

Since 2026-10-13, `/api/services/produits` without a `page` parameter stops at 300 artworks and returns `hasMore: true`. The script asks for every page of 15 (numbered from 0, with `seed=0` so the order stays stable). Without this, the run stops with "Seulement 300 oeuvres renvoyees" and no file is written.

## Sold artworks stay out

An original sells once. Artworks the API marks as not in stock (`en_stock` false) are sold, so the script leaves them out of every file, along with artworks priced at 0. Meta then removes them from the catalog on the next fetch.

## Rules that must not change

- Ids are `LORIGINAL-<artwork id>-FR`. The Meta pixel sends this exact format from GTM. If the format changes, retargeting stops matching.
- `custom_label_0` to `custom_label_4` hold the site categories (styles, themes, sizes, price bands, in stock). The category ad sets use them through product sets. Values look like `|abstrait|street-art|`.
- The script only reads public data and writes files. It needs no secret.

## Run it by hand

```
pip install requests
python meta_flux_catalogue.py flux
```

Or open the Actions tab and run "Meta catalog feed".

## Future

This is a stopgap. The long-term home is a feed route on loriginal.org (Artur-art-team/react#1842). When it exists, point both Meta feeds at it and archive this repo.
