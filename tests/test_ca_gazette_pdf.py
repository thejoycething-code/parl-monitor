"""Canada Gazette PDF-only issues (src/ca_gazette_pdf.py). No network.

The page texts below are cut from what english_pages() returned for the real
issues of 5 June 2010 (Part I, g1-14423.pdf) and 9 June 2010 (Part II,
g2-14412.pdf), read 28 September 2026.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_gazette_pdf as P  # noqa: E402


def make_pdf(pages):
    """A minimal PDF: `pages` is a list of pages, each a list of (x, y, text)
    runs in Helvetica. Enough for pypdf to extract, positioned like a Gazette
    page (612 pt wide, English at x=48, French at x=312)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None,
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for runs in pages:
        # Each run placed by its own text matrix (Tm), as the Gazette's are.
        stream = "".join("BT /F1 9 Tf 1 0 0 1 {0} {1} Tm ({2}) Tj ET\n".format(x, y, t)
                         for x, y, t in runs)
        objs.append("<< /Length {0} >>\nstream\n{1}endstream".format(len(stream), stream))
        content = len(objs)
        objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    "/Resources << /Font << /F1 3 0 R >> >> /Contents {0} 0 R >>".format(content))
        kids.append(len(objs))
    objs[1] = "<< /Type /Pages /Kids [{0}] /Count {1} >>".format(
        " ".join("{0} 0 R".format(k) for k in kids), len(kids))
    out, offsets = "%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out.encode("latin-1")))
        out += "{0} 0 obj\n{1}\nendobj\n".format(i, body)
    xref = len(out.encode("latin-1"))
    out += "xref\n0 {0}\n0000000000 65535 f \n".format(len(objs) + 1)
    out += "".join("{0:010d} 00000 n \n".format(o) for o in offsets)
    out += "trailer\n<< /Size {0} /Root 1 0 R >>\nstartxref\n{1}\n%%EOF\n".format(len(objs) + 1, xref)
    return out.encode("latin-1")


P1_PAGES = [
    "Vol. 144, No. 23  Vol. 144, no 23\nCanada \nGazette \nPart I \n",
    " Le 5 juin 2010 Gazette du Canada Partie I  1399 \nTABLE OF CONTENTS   TABLE DES MATIÈRES  \n"
    "Government notices .........................................................  1400 Avis du gouvernement\n"
    "Commissions ...................................................................  1401 Commissions\n"
    "Proposed regulations .......................................................  1402 Règlements projetés\n",
    " 1400 Canada Gazette Part I June 5, 2010\nGOVERNMENT NOTICES \n"
    "DEPARTMENT OF THE ENVIRONMENT MINISTÈRE DE L’ENVIRONNEMENT \n"
    "KYOTO PROTOCOL IMPLEMENTATION ACT LOI DE MISE EN ŒUVRE DU PROTOCOLE DE KYOTO \n"
    "Notice  Avis  \nNotice is hereby given, under paragraph 5(3)(b) of the Kyoto \n"
    "Protocol Implementation Act, that a plan has been prepared.\nJIM PRENTICE \n"
    "[23-1-o] [23-1-o] \n",
    " Le 5 juin 2010 Gazette du Canada Partie I  1401 \nCOMMISSIONS COMMISSIONS \n"
    "CANADA REVENUE AGENCY \nINCOME TAX ACT \n"
    "Revocation of registration of charities \n"
    "The following notice of proposed revocation was sent to the charity listed below \n"
    "because it has not met the filing requirements of the Income Tax Act.\n[23-1]\n"
    "PARIS RE PARIS RE \nRELEASE OF ASSETS LIBÉRATION D’ACTIF \n"
    "Notice is hereby given that Paris Re intends to apply for the release of its assets.\n"
    "[23-1-o] \n",
    " 1402 Canada Gazette Part I June 5, 2010\nPROPOSED REGULATIONS \nTable of Contents \nPage \n"
    "Health, Dept. of \nRegulations Amending the Assisted Human Reproduction ......... 1402 \n"
    "Règlement modifiant le Règlement \n"
    "Regulations Amending the Assisted Human Reproduction \n(Section 8 Consent) Regulations \n"
    "Statutory authority Fondement législatif \nAssisted Human Reproduction Act \n"
    "REGULATORY IMPACT ANALYSIS STATEMENT \n"
    "Interested persons may make representations within 75 days after the date of publication of this notice.\n"
    "[23-1-o] [23-1-o]\n",
    " Le 5 juin 2010 Gazette du Canada Partie I 1403 \nINDEX \nVol. 144, No. 23 — June 5, 2010 \n"
    "AVIS DIVERS \n* B2B Trust, lettres patentes de prorogation ........................   1488 \n",
]

P2_PAGES = [
    "Canada \nGazette \nPart II \nOTTAWA, WEDNESDAY, JUNE 9, 2010  OTTAWA, LE MERCREDI 9 JUIN 2010\n"
    "SOR/2010-110 to 117 and SI/2010-42  DORS/2010-110 à 117 et TR/2010-42\n",
    "2010-06-09 Canada Gazette Part II, Vol. 144, No. 12 Gazette du Canada Partie II, Vol. 144, n o 12 \n"
    "942 \nRegistration Enregistrement \nSOR/2010-110 May 19, 2010 DORS/2010-110 Le 19 mai 2010 \n"
    "RAILWAY SAFETY ACT LOI SUR LA SÉCURITÉ FERROVIAIRE \n"
    "Notice Respecting the 2010 G8 and G20 Summits \nRailway Transportation Security Measures \n"
    "The Minister of Transport, pursuant to subsection 39.1(2) of the Railway Safety Act, issues the notice.\n",
    "2010-06-09 Canada Gazette Part II, Vol. 144, No. 12 Gazette du Canada Partie II, Vol. 144, n o 12 \n"
    "Registration Enregistrement \nSOR/2010-114 May 27, 2010 DORS/2010-114 Le 27 mai 2010 \n"
    "FOOD AND DRUGS ACT LOI SUR LES ALIMENTS ET DROGUES \n"
    "Regulations Amending the Food and Drug \nRegulations (1595 — Schedule F) \n"
    "P.C. 2010-675 May 27, 2010 \nHis Excellency the Governor General in Council makes the annexed Regulations.\n",
    "\nTABLE OF CONTENTS SOR: Statutory Instruments (Regulations) \n"
    "SOR/2010-110 Transport Notice Respecting the 2010 G8 ............. 942\n",
]


class EnglishOnlyTests(unittest.TestCase):
    def test_the_french_half_of_a_merged_line_is_cut(self):
        for line, english in [
                ("PARIS RE PARIS RE", "PARIS RE"),
                ("Notice  Avis", "Notice"),
                ("RELEASE OF ASSETS LIBÉRATION D’ACTIF", "RELEASE OF ASSETS"),
                ("Greenhouse bell peppers Poivrons de serre", "Greenhouse bell peppers"),
                ("LETTERS PATENT OF CONTINUANCE LETTRES PATENTES DE PROROGATION",
                 "LETTERS PATENT OF CONTINUANCE"),
                ("FORD CREDIT CANADA LIMITED CRÉDIT FORD DU CANADA LIMITÉE", "FORD CREDIT CANADA LIMITED"),
                ("DEPARTMENT OF THE ENVIRONMENT MINISTÈRE DE L’ENVIRONNEMENT",
                 "DEPARTMENT OF THE ENVIRONMENT")]:
            self.assertEqual(P.english_only(line), english, line)

    def test_an_english_line_is_left_whole(self):
        for line in ["Revocation of registration of charities",
                     "Monitoring of Medical Assistance in Dying Regulations",
                     "CANADIAN ENVIRONMENTAL PROTECTION ACT, 1999"]:
            self.assertEqual(P.english_only(line), line)


class PartOneTests(unittest.TestCase):
    def setUp(self):
        self.items = P.items(P1_PAGES, 1, "https://gazette.gc.ca/rp-pr/p1/2010/2010-06-05/pdf/g1-14423.pdf")

    def test_one_item_per_insertion_code_and_the_cover_and_index_are_dropped(self):
        self.assertEqual([i["title"] for i in self.items], [
            "KYOTO PROTOCOL IMPLEMENTATION ACT — Notice",
            "Revocation of registration of charities",
            "RELEASE OF ASSETS",
            "Regulations Amending the Assisted Human Reproduction (Section 8 Consent) Regulations"])

    def test_the_section_comes_from_the_table_of_contents_page(self):
        self.assertEqual([i["section"] for i in self.items],
                         ["Government notices", "Commissions", "Commissions", "Proposed regulations"])

    def test_the_url_names_the_page_and_two_items_on_one_page_are_told_apart(self):
        self.assertEqual([i["url"].split("#")[1] for i in self.items],
                         ["page=3", "page=4", "page=4.2", "page=5"])

    def test_a_proposed_regulation_is_a_regulation_and_keeps_its_text(self):
        reg = self.items[-1]
        self.assertEqual(reg["kind"], "regulation")
        self.assertIn("within 75 days after the date of publication", reg["text"])
        self.assertEqual(self.items[1]["department"], "CANADA REVENUE AGENCY")

    def test_running_heads_do_not_reach_the_text(self):
        self.assertFalse(any("Gazette du Canada Partie I" in i["text"] for i in self.items))


class PartTwoTests(unittest.TestCase):
    def test_one_item_per_registration_with_its_number_and_title(self):
        items = P.items(P2_PAGES, 2, "https://gazette.gc.ca/rp-pr/p2/2010/2010-06-09/pdf/g2-14412.pdf")
        self.assertEqual([(i["registration"], i["department"], i["title"], i["kind"]) for i in items], [
            ("SOR/2010-110", "RAILWAY SAFETY ACT",
             "Notice Respecting the 2010 G8 and G20 Summits Railway Transportation Security Measures",
             "regulation"),
            ("SOR/2010-114", "FOOD AND DRUGS ACT",
             "Regulations Amending the Food and Drug Regulations (1595 — Schedule F)", "regulation")])
        self.assertNotIn("TABLE OF CONTENTS", items[-1]["text"], "the last item stops at the back matter")
        self.assertNotIn("DORS/2010-110", items[0]["text"][:40])

    def test_an_issue_with_no_boundaries_is_one_extra_item(self):
        items = P.items(["Order fixing the day on which the Act comes into force."], 2,
                        "https://gazette.gc.ca/x.pdf", title="Part II, volume 144, Extra number 1")
        self.assertEqual([(i["kind"], i["title"]) for i in items],
                         [("extra", "Part II, volume 144, Extra number 1")])


class ColumnTests(unittest.TestCase):
    def test_only_the_left_column_is_read(self):
        pdf = make_pdf([[(48, 700, "Revocation of registration of charities"),
                         (312, 700, "Revocation de l'enregistrement d'organismes de bienfaisance"),
                         (48, 680, "The charity listed below"), (321, 680, "L'organisme ci-dessous")]])
        text = P.english_pages(pdf)[0]
        self.assertIn("Revocation of registration of charities", text)
        self.assertIn("The charity listed below", text)
        self.assertNotIn("bienfaisance", text)
        self.assertNotIn("ci-dessous", text)


if __name__ == "__main__":
    unittest.main()
