"""
PubMed (NCBI) Sığır, Koyun, Keçi ve Besi Hekimliği Makale Toplayıcısı
Resmi E-utilities API + Otomatik Türkçe Çeviri + 30 Günlük Filtre
"""

import logging
from typing import List, Dict, Any
import requests

from config import DEFAULT_HEADERS, HTTP_TIMEOUT, is_acceptable_news, get_priority
from translator import translate_to_turkish

logger = logging.getLogger("vet_bot.pubmed")

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Angus Sığırı (Besi Boğası, Düve) ve Buzağı Odaklı Arama Terimleri (Mastitis elendi)
SEARCH_QUERIES = [
    "Angus cattle beef feedlot performance carcass growth",
    "bovine respiratory disease calves BRD treatment vaccine",
    "beef calf diarrhea scour colostrum health immunology",
    "beef cattle feedlot acidosis rumen health nutrition",
    "Angus heifer reproductive performance calving growth",
    "bovine viral diarrhea BVD calf health feedlot"
]


def fetch_pubmed_articles() -> List[Dict[str, Any]]:
    """PubMed üzerinden sığır, koyun, keçi ve besi hekimliği makalelerini çeker ve Türkçe'ye çevirir."""
    items: List[Dict[str, Any]] = []
    seen_pmids = set()

    for query in SEARCH_QUERIES:
        try:
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": 5,
                "sort": "pub_date"
            }
            resp = requests.get(PUBMED_SEARCH_URL, params=search_params, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
            if resp.status_code != 200:
                continue

            search_data = resp.json()
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            new_ids = [pid for pid in id_list if pid not in seen_pmids]
            if not new_ids:
                continue

            seen_pmids.update(new_ids)

            summary_params = {
                "db": "pubmed",
                "id": ",".join(new_ids),
                "retmode": "json"
            }
            sum_resp = requests.get(PUBMED_SUMMARY_URL, params=summary_params, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
            if sum_resp.status_code != 200:
                continue

            sum_data = sum_resp.json().get("result", {})

            for pid in new_ids:
                doc = sum_data.get(pid)
                if not doc:
                    continue

                title = doc.get("title", "").strip().rstrip(".")
                pubdate = doc.get("pubdate", "")
                source_journal = doc.get("source", "PubMed")
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"

                if not title:
                    continue

                # SIKI SÜZGEÇ: Sadece hedef hayvanlar & taziye/gürültü yok
                if not is_acceptable_news(title, source_journal, "PubMed", pub_date=pubdate, url=link):
                    continue

                # Otomatik Türkçe Çeviri
                tr_title, was_en = translate_to_turkish(title)

                display_title = f"🔬 [PubMed - Türkçe] {tr_title}"
                if was_en and tr_title != title:
                    display_title += f"\n<i>(Orijinal: {title[:75]}...)</i>"

                items.append({
                    "title": display_title,
                    "link": link,
                    "source": f"PubMed ({source_journal})",
                    "category": "ACADEMIC",
                    "priority": get_priority("ACADEMIC"),
                    "summary": f"Yayın Tarihi: {pubdate} | Dergi: {source_journal}",
                    "published_at": pubdate
                })

        except Exception as e:
            logger.error(f"PubMed makalesi ({query}) hatası: {e}")

    return items
