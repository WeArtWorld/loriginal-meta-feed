"""Genere le flux catalogue Meta de L'Original depuis l'API publique du site.

Produit quatre fichiers dans le dossier de sortie (defaut : ./flux) :
    catalogue-fr.csv             flux principal, une ligne par oeuvre publiee
    catalogue-en.csv             surcharge de langue en_XX (memes id, titre et lien anglais)
    catalogue-pinterest-fr.csv   flux Pinterest francais complet
    catalogue-pinterest-en.csv   flux Pinterest anglais complet (memes id, textes et liens anglais)

Les flux Pinterest retirent les oeuvres de exclusions-pinterest.txt (nus et
autres sujets refuses par les consignes marchandes de Pinterest) et les prix nuls.

Les id restent au format deja utilise par le catalogue et le pixel :
LORIGINAL-<id>-FR. Les etiquettes custom_label_0..4 portent les categories du
site, pour les groupes d'oeuvres des pubs par categorie :
    0 styles   1 themes   2 tailles   3 tranches de prix   4 en-ligne

Ne lit que des donnees publiques ; ecrit seulement des fichiers locaux.
    python meta_flux_catalogue.py [dossier_de_sortie]
"""

import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

API = "https://www.loriginal.org/api/services/produits"
SITE = "https://www.loriginal.org"

STYLES = {"abstrait": "abstrait", "impressionnisme": "impressionnisme", "minimaliste": "minimaliste",
          "street-art": "art-de-la-rue", "surrealisme": "surrealiste"}
THEMES = {"calme": "Calm", "romantique": "Love", "pop": "Cinema & TV", "paysages": "Landscape",
          "portraits": "Portrait", "animaux": "Animals"}
TAILLES = {"grand": "large", "petit": "small", "mini": "mini"}
PLAFONDS = (500, 1000, 1750, 2500, 4000)
# Meta n'accepte que ses propres codes pour une surcharge de langue (en_XX, pas en_US).
LANGUE_EN = "en_XX"

SUPPORTS_FR = {"Canvas": "toile", "Paper": "papier", "Wood": "bois", "Metal": "métal", "Panel": "panneau"}

COLONNES = ["id", "title", "description", "availability", "condition", "price", "link", "image_link",
            "additional_image_link", "brand", "product_type", "google_product_category",
            "custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3", "custom_label_4"]
COLONNES_EN = ["id", "override", "title", "description", "link"]
EXCLUSIONS_PINTEREST = Path(__file__).with_name("exclusions-pinterest.txt")


def exclusions_pinterest() -> set[str]:
    if not EXCLUSIONS_PINTEREST.exists():
        return set()
    lignes = EXCLUSIONS_PINTEREST.read_text(encoding="utf-8").splitlines()
    return {l.split("#")[0].strip() for l in lignes if l.split("#")[0].strip()}


def page(numero: int, params: dict) -> dict:
    for essai in range(3):
        try:
            r = requests.get(API, params={**params, "page": numero, "seed": 0}, timeout=300)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if essai == 2:
                raise


def lister(**params) -> list[dict]:
    # Depuis le 2026-10-13, la route sans "page" s'arrete a 300 oeuvres (hasMore) :
    # on demande donc chaque page de 15, numerotees a partir de 0.
    premiere = page(0, params)
    pages = -(-int(premiere.get("total") or 0) // 15)
    with ThreadPoolExecutor(8) as pool:
        suite = list(pool.map(lambda n: page(n, params), range(1, pages)))
    vus, produits = set(), []
    for p in [premiere, *suite]:
        for o in p.get("produits", []):
            if o["id"] not in vus:
                vus.add(o["id"])
                produits.append(o)
    return produits


def cm(pouces) -> int | None:
    try:
        return round(float(pouces) * 2.54)
    except (TypeError, ValueError):
        return None


def etiquette(codes: list[str]) -> str:
    return f"|{'|'.join(codes)}|" if codes else ""


def bandes_prix(dollars: float) -> list[str]:
    if dollars >= 5000:
        return ["5000-plus"]
    return [str(p) for p in PLAFONDS if dollars <= p]


def images(o: dict) -> tuple[str, str]:
    principale = o.get("url_image_oeuvre") or ""
    autres = []
    for im in o.get("images") or []:
        url = im.get("url") if isinstance(im, dict) else im
        if isinstance(url, str) and url and url != principale:
            autres.append(url)
    return principale, ",".join(autres[:10])


def description(o: dict, langue: str) -> str:
    artiste = (o.get("artiste") or {}).get("nom") or "L'Original"
    l, h = cm(o.get("largeur")), cm(o.get("hauteur"))
    taille = f"{l} x {h} cm" if l and h else ""
    technique = o.get("technique") or ""
    support = o.get("support") or ""
    if langue == "fr":
        titre = o.get("nom") or o.get("nom_en") or ""
        sur = SUPPORTS_FR.get(support, support.lower())
        morceaux = [f"{titre}, oeuvre originale de {artiste}", f"{technique} sur {sur}".strip(" sur") if technique or sur else "", taille]
        fin = "Pièce unique, certificat d'authenticité signé, livraison partout au Canada."
    else:
        titre = o.get("nom_en") or o.get("nom") or ""
        morceaux = [f"{titre}, an original artwork by {artiste}", f"{technique} on {support.lower()}".strip(" on") if technique or support else "", taille]
        fin = "One of a kind, signed certificate of authenticity, delivered across Canada."
    return ". ".join(m for m in morceaux if m) + ". " + fin


def main() -> None:
    sortie = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("flux"))
    sortie.mkdir(parents=True, exist_ok=True)

    oeuvres = lister()
    if len(oeuvres) < 500:
        sys.exit(f"Seulement {len(oeuvres)} oeuvres renvoyees : l'API semble en panne, flux non ecrit.")

    membres: dict[str, dict[str, set[int]]] = {"styles": {}, "themes": {}, "tailles": {}}
    for famille, table, param in (("styles", STYLES, "styles"), ("themes", THEMES, "themes"), ("tailles", TAILLES, "size")):
        for code, valeur in table.items():
            membres[famille][code] = {o["id"] for o in lister(**{param: valeur})}

    exclues = exclusions_pinterest()
    lignes_fr, lignes_en, pinterest_fr, pinterest_en = [], [], [], []
    for o in oeuvres:
        oid = o["id"]
        if o.get("prix") in (None, "") or not o.get("url_image_oeuvre"):
            continue
        dollars = float(o["prix"]) / 100
        en_stock = o.get("en_stock") not in (False, 0, "0", None)
        slug = (o.get("slug") or "").strip() or str(oid)
        image, autres = images(o)

        def codes(famille: str) -> list[str]:
            return [c for c, ids in membres[famille].items() if oid in ids]

        rid = f"LORIGINAL-{oid}-FR"
        lignes_fr.append({
            "id": rid,
            "title": (o.get("nom") or o.get("nom_en") or f"Oeuvre {oid}")[:150],
            "description": description(o, "fr")[:5000],
            "availability": "in stock" if en_stock else "out of stock",
            "condition": "new",
            "price": f"{dollars:.2f} CAD",
            "link": f"{SITE}/fr/peinture/{slug}",
            "image_link": image,
            "additional_image_link": autres,
            "brand": (o.get("artiste") or {}).get("nom") or "L'Original",
            "product_type": "Art > Peintures originales",
            "google_product_category": "500044",
            "custom_label_0": etiquette(codes("styles")),
            "custom_label_1": etiquette(codes("themes")),
            "custom_label_2": etiquette(codes("tailles")),
            "custom_label_3": etiquette(bandes_prix(dollars)),
            "custom_label_4": "en-ligne" if en_stock else "",
        })
        lignes_en.append({
            "id": rid,
            "override": LANGUE_EN,
            "title": (o.get("nom_en") or o.get("nom") or f"Artwork {oid}")[:150],
            "description": description(o, "en")[:5000],
            "link": f"{SITE}/en/painting/{slug}",
        })
        if rid not in exclues and dollars > 0:
            pinterest_fr.append(lignes_fr[-1])
            pinterest_en.append({**lignes_fr[-1],
                                 "title": lignes_en[-1]["title"],
                                 "description": lignes_en[-1]["description"],
                                 "link": lignes_en[-1]["link"],
                                 "product_type": "Art > Original paintings"})

    ids_fr = {l["id"] for l in lignes_fr}
    if any(l["id"] not in ids_fr or l["override"] != LANGUE_EN for l in lignes_en):
        sys.exit("Flux EN incoherent avec le flux FR (id absent ou code de langue invalide) : flux non ecrit.")

    for nom, colonnes, lignes in (("catalogue-fr.csv", COLONNES, lignes_fr), ("catalogue-en.csv", COLONNES_EN, lignes_en),
                                  ("catalogue-pinterest-fr.csv", COLONNES, pinterest_fr),
                                  ("catalogue-pinterest-en.csv", COLONNES, pinterest_en)):
        with (sortie / nom).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=colonnes)
            w.writeheader()
            w.writerows(lignes)

    en_ligne = sum(1 for l in lignes_fr if l["custom_label_4"])
    print(f"{len(lignes_fr)} oeuvres ecrites ({en_ligne} en stock) dans {sortie}, "
          f"{len(pinterest_fr)} pour Pinterest ({len(exclues)} exclusions)")


if __name__ == "__main__":
    main()
