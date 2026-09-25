# L'Original: Meta catalog feed

This repo builds the product feed for the Meta catalog "L'Original — Œuvres" (`598914184189673`).

Every night at 07:17 UTC, a GitHub Action reads the public artwork API on loriginal.org, writes two CSV files to `flux/`, and commits them. Meta fetches these files every day.

| File | Meta feed | What it holds |
|---|---|---|
| `flux/catalogue-fr.csv` | `Flux Merchant Center FR` (primary) | One row per published artwork, in French |
| `flux/catalogue-en.csv` | `Traductions EN (en_US)` (language override) | English title, description and link for the same ids |

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
