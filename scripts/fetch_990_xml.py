"""
Fetch 990 XML filings for a specific EIN from the IRS bulk data.

Usage:
    python scripts/fetch_990_xml.py --ein 123456789 --years 2018 2019 2020 2021 2022 2023
    python scripts/fetch_990_xml.py --ein 123456789  # defaults to 2018-2025

Downloads each matching XML to: private/example documents/990_xml/

How it works:
    1. Downloads the index CSV for each year (~5-15MB each)
    2. Scans for rows matching the EIN
    3. Constructs the XML URL from the OBJECT_ID column
    4. Downloads and saves each XML filing
"""

import argparse
import csv
import io
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

INDEX_URL  = "https://apps.irs.gov/pub/epostcard/990/xml/{year}/index_{year}.csv"
ZIP_URL    = "https://apps.irs.gov/pub/epostcard/990/xml/{year}/{year}_TEOS_XML_{suffix}.zip"
# All possible monthly ZIP suffixes — search in most-likely-first order.
# Some months have B/C variants when a single month's data spans multiple archives.
ZIP_SUFFIXES = [
    "09A","09B","10A","10B","11A","11B","08A","08B",
    "07A","07B","12A","12B","06A","06B","05A","05B",
    "04A","04B","03A","03B","02A","02B","01A","01B",
    "CT1","CT2",  # older format used in 2019-2020
]

DEFAULT_YEARS = list(range(2018, 2026))


class HTTPRangeFile:
    """File-like object backed by HTTP range requests — lets zipfile read a remote ZIP's
    central directory without downloading the full archive."""
    def __init__(self, url: str):
        self.url  = url
        self._pos = 0
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            self._size = int(r.headers["Content-Length"])

    def read(self, n=-1):
        if n == -1:
            n = self._size - self._pos
        if n == 0:
            return b""
        end = min(self._pos + n - 1, self._size - 1)
        req = urllib.request.Request(self.url, headers={
            "User-Agent": "Mozilla/5.0",
            "Range": f"bytes={self._pos}-{end}",
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        self._pos += len(data)
        return data

    def seek(self, pos, whence=0):
        if whence == 0:   self._pos = pos
        elif whence == 1: self._pos += pos
        elif whence == 2: self._pos = self._size + pos
        return self._pos

    def tell(self):      return self._pos
    def seekable(self):  return True
    def readable(self):  return True


def fetch_url(url: str, label: str) -> bytes | None:
    """Download a URL and return the raw bytes, or None on failure."""
    print(f"  Fetching {label}...", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        print(f"OK ({len(data):,} bytes)")
        return data
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def find_and_extract_from_zip(year: int, object_id: str, output_dir: Path,
                               period: str, form_type: str,
                               force_suffix: str = "") -> bool:
    """Search monthly ZIP archives for object_id and extract the XML file.
    Returns True if extracted successfully."""
    fname = output_dir / f"990_{object_id}_{period}_{form_type}.xml"
    if fname.exists():
        print(f"  Already exists: {fname.name}")
        return True

    suffixes_to_try = [force_suffix] if force_suffix else ZIP_SUFFIXES
    for suffix in suffixes_to_try:
        zip_url = ZIP_URL.format(year=year, suffix=suffix)
        inner   = f"{year}_TEOS_XML_{suffix}/{object_id}_public.xml"
        try:
            f  = HTTPRangeFile(zip_url)
            zf = zipfile.ZipFile(f)
            if inner not in zf.namelist():
                continue
            # Found it — extract
            print(f"  Extracting from {year}_TEOS_XML_{suffix}.zip...", end=" ", flush=True)
            data = zf.read(inner)
            fname.write_bytes(data)
            print(f"OK ({len(data):,} bytes) -> {fname.name}")
            return True
        except urllib.error.HTTPError:
            continue  # This monthly ZIP doesn't exist
        except Exception as e:
            print(f"  Error in {suffix}: {e}")
            continue

    print(f"  NOT FOUND in any ZIP for year {year}: {object_id}")
    return False


def find_filings_in_index(index_bytes: bytes, ein: str, debug: bool = False) -> list[dict]:
    """Parse the index CSV and return all rows matching the EIN."""
    matches = []
    ein_clean = ein.replace("-", "")

    text = index_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    if debug:
        # Show column names so we can verify field mapping
        print(f"    CSV columns: {reader.fieldnames}")

    for row in reader:
        # Try both common column name variants
        row_ein = (row.get("EIN") or row.get("ein") or "").replace("-", "").strip()
        if row_ein == ein_clean:
            if debug and not matches:
                print(f"    Sample row: {dict(row)}")
            matches.append({
                "object_id":   (row.get("OBJECT_ID") or "").strip(),
                "form_type":   (row.get("RETURN_TYPE") or row.get("FORM_TYPE") or "").strip(),
                "ein":         row_ein,
                "tax_period":  (row.get("TAX_PERIOD") or "").strip(),
                "sub_date":    (row.get("SUB_DATE") or "").strip(),
                "org_name":    (row.get("TAXPAYER_NAME") or "").strip(),
                "xml_batch_id":(row.get("XML_BATCH_ID") or "").strip(),  # 2024+ only
            })
    return matches


def fetch_filings(ein: str, years: list[int], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ein_clean = ein.replace("-", "")

    all_filings = []

    for year in years:
        print(f"\n--- Year {year} ---")
        index_url = INDEX_URL.format(year=year)
        index_bytes = fetch_url(index_url, f"index_{year}.csv")
        if not index_bytes:
            continue

        matches = find_filings_in_index(index_bytes, ein_clean, debug=True)
        if not matches:
            print(f"  No filings found for EIN {ein_clean} in {year}")
            continue

        print(f"  Found {len(matches)} filing(s):")
        for m in matches:
            print(f"    {m['org_name']} | {m['form_type']} | period {m['tax_period']} | filed {m['sub_date']}")
            all_filings.append((year, m))

    if not all_filings:
        print(f"\nNo filings found for EIN {ein_clean} across years {years[0]}-{years[-1]}")
        return

    print(f"\n--- Extracting {len(all_filings)} XML file(s) from IRS ZIP archives ---")
    for year, filing in all_filings:
        object_id = filing["object_id"]
        if not object_id:
            print(f"  SKIP -- no object_id for {filing['tax_period']}")
            continue

        # 2024+ index includes XML_BATCH_ID — use it directly instead of searching
        batch_id = filing.get("xml_batch_id", "")
        if batch_id:
            suffix = batch_id.replace(f"{year}_TEOS_XML_", "")
            find_and_extract_from_zip(
                year=year, object_id=object_id, output_dir=output_dir,
                period=filing["tax_period"], form_type=filing["form_type"] or "990",
                force_suffix=suffix,
            )
        else:
            find_and_extract_from_zip(
                year=year, object_id=object_id, output_dir=output_dir,
                period=filing["tax_period"], form_type=filing["form_type"] or "990",
            )

    print(f"\nDone. Files saved to: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Fetch 990 XML filings from IRS bulk data")
    parser.add_argument("--ein",   required=True, help="EIN without dashes, e.g. 123456789")
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS,
                        help="Tax years to search (default: 2018-2025)")
    parser.add_argument("--out",   default=None,
                        help="Output directory (default: private/example documents/990_xml/)")
    args = parser.parse_args()

    # Default output directory relative to project root
    if args.out:
        output_dir = Path(args.out)
    else:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        output_dir = project_root / "private" / "example documents" / "990_xml"

    print(f"EIN: {args.ein}")
    print(f"Years: {args.years}")
    print(f"Output: {output_dir}")

    fetch_filings(args.ein, sorted(args.years), output_dir)


if __name__ == "__main__":
    main()
