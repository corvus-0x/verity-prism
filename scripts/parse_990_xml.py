"""
Parse all 990 XML files and display key fields across all years.
Usage: python scripts/parse_990_xml.py
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from glob import glob

NS = "{http://www.irs.gov/efile}"


def tx(el, path):
    """Get text from a dotted path of child elements."""
    cur = el
    for part in path.split("."):
        found = cur.find(f"{NS}{part}")
        if found is None:
            return ""
        cur = found
    return (cur.text or "").strip()


def amt(el, path):
    v = tx(el, path)
    try:
        return int(v)
    except (ValueError, TypeError):
        return v or 0


def yn(el, path):
    v = tx(el, path).lower()
    if v == "true":  return "YES"
    if v == "false": return "NO"
    return v.upper() or "-"


def fmt(v):
    if isinstance(v, int):
        return f"${v:>12,}"
    return f"{v:>13}"


def parse_file(fpath):
    fname = Path(fpath).name
    tree  = ET.parse(fpath)
    root  = tree.getroot()

    hdr   = root.find(f"{NS}ReturnHeader")
    data  = root.find(f"{NS}ReturnData")
    f990  = data.find(f"{NS}IRS990") if data is not None else None
    f990t = data.find(f"{NS}IRS990T") if data is not None else None

    form_type   = tx(hdr, "ReturnTypeCd")
    tax_year    = tx(hdr, "TaxYr")
    period      = tx(hdr, "TaxPeriodEndDt")
    filed_ts    = tx(hdr, "ReturnTs")[:10] if tx(hdr, "ReturnTs") else ""
    org_name    = tx(hdr, "Filer.BusinessName.BusinessNameLine1Txt")
    address     = tx(hdr, "Filer.USAddress.AddressLine1Txt")
    city        = tx(hdr, "Filer.USAddress.CityNm")
    officer     = tx(hdr, "BusinessOfficerGrp.PersonNm")
    title       = tx(hdr, "BusinessOfficerGrp.PersonTitleTxt")
    sign_date   = tx(hdr, "BusinessOfficerGrp.SignatureDt")
    preparer_nm = tx(hdr, "PreparerPersonGrp.PreparerPersonNm")
    prep_firm   = tx(hdr, "PreparerFirmGrp.PreparerFirmName.BusinessNameLine1Txt")

    sep = "=" * 72
    print(sep)
    print(f"FILE:    {fname}")
    print(f"Form:    {form_type}   Tax Year: {tax_year}   Period End: {period}")
    print(f"Signed:  {sign_date}   (timestamp: {filed_ts})")
    print(f"Org:     {org_name}")
    print(f"Address: {address}, {city}")
    print(f"Officer: {officer} ({title})")
    print(f"Preparer: {preparer_nm} / {prep_firm}")

    if f990 is not None:

        # ── Revenue ──────────────────────────────────────────────────────────
        print("\n  REVENUE")
        print(f"  Gross Receipts:            {fmt(amt(f990,'GrossReceiptsAmt'))}")
        print(f"  Contributions (CY):        {fmt(amt(f990,'CYContributionsGrantsAmt'))}")
        print(f"  Prog Svc Revenue (CY):     {fmt(amt(f990,'CYProgramServiceRevenueAmt'))}")
        print(f"  Gross UBI:                 {fmt(amt(f990,'TotalGrossUBIAmt'))}")
        print(f"  Total Revenue (CY):        {fmt(amt(f990,'CYTotalRevenueAmt'))}")
        print(f"  Total Revenue (PY):        {fmt(amt(f990,'PYTotalRevenueAmt'))}")

        # ── Expenses ─────────────────────────────────────────────────────────
        print("\n  EXPENSES")
        print(f"  Salaries (CY):             {fmt(amt(f990,'CYSalariesCompEmpBnftPaidAmt'))}")
        print(f"  Total Expenses (CY):       {fmt(amt(f990,'CYTotalExpensesAmt'))}")
        print(f"  Net Income (CY):           {fmt(amt(f990,'CYRevenuesLessExpensesAmt'))}")

        # ── Balance Sheet ─────────────────────────────────────────────────────
        print("\n  BALANCE SHEET")
        print(f"  Total Assets BOY:          {fmt(amt(f990,'TotalAssetsBOYAmt'))}")
        print(f"  Total Assets EOY:          {fmt(amt(f990,'TotalAssetsEOYAmt'))}")
        print(f"  Land+Bldg Cost Basis:      {fmt(amt(f990,'LandBldgEquipCostOrOtherBssAmt'))}")
        print(f"  Land+Bldg Net EOY:         {fmt(amt(f990,'LandBldgEquipBasisNetGrp.EOYAmt'))}")
        print(f"  Total Liabilities EOY:     {fmt(amt(f990,'TotalLiabilitiesEOYAmt'))}")
        print(f"  Net Assets BOY:            {fmt(amt(f990,'NetAssetsOrFundBalancesBOYAmt'))}")
        print(f"  Net Assets EOY:            {fmt(amt(f990,'NetAssetsOrFundBalancesEOYAmt'))}")

        # ── People ────────────────────────────────────────────────────────────
        print("\n  PEOPLE / GOVERNANCE")
        print(f"  Employees:                 {amt(f990,'TotalEmployeeCnt')}")
        print(f"  Volunteers:                {amt(f990,'TotalVolunteersCnt')}")
        print(f"  Board Members (total):     {amt(f990,'VotingMembersGoverningBodyCnt')}")
        print(f"  Board Members (indep):     {amt(f990,'VotingMembersIndependentCnt')}")

        officers = f990.findall(f"{NS}Form990PartVIISectionAGrp")
        if officers:
            print("  Officers:")
            for o in officers:
                nm    = tx(o, "PersonNm")
                titl  = tx(o, "TitleTxt")
                comp  = amt(o, "ReportableCompFromOrgAmt")
                hrs   = tx(o, "AverageHoursPerWeekRt")
                comp_s = f"${comp:,}" if isinstance(comp, int) else str(comp)
                hrs_s  = f"{hrs} hrs/wk" if hrs else ""
                print(f"    {nm:<28} {titl:<22} comp={comp_s:<12} {hrs_s}")

        # ── Governance flags ──────────────────────────────────────────────────
        print("\n  GOVERNANCE FLAGS")
        flags = [
            ("Conflict of Interest Policy",  "ConflictOfInterestPolicyInd"),
            ("Whistleblower Policy",          "WhistleblowerPolicyInd"),
            ("Document Retention Policy",     "DocumentRetentionPolicyInd"),
            ("CEO Compensation Process",      "CompensationProcessCEOInd"),
            ("Audit of Financial Statements", "FSAuditedInd"),
            ("Related Entity Exists",         "RelatedEntityInd"),
            ("Business Rln w/ Org Members",   "BusinessRlnWithOrgMemInd"),
            ("Business Rln w/ Family",        "BusinessRlnWithFamMemInd"),
            ("Excess Benefit Transactions",   "EngagedInExcessBenefitTransInd"),
            ("Loan to Officer Outstanding",   "LoanOutstandingInd"),
            ("Grant to Related Person",       "GrantToRelatedPersonInd"),
            ("Transfer to Non-Charitable",    "TrnsfrExmptNonChrtblRltdOrgInd"),
        ]
        for label, path in flags:
            print(f"  {label:<38} {yn(f990, path)}")

        # ── Program service revenue ───────────────────────────────────────────
        psrvs = f990.findall(f"{NS}ProgramServiceRevenueGrp")
        if psrvs:
            print("\n  PROGRAM SERVICE REVENUE")
            for ps in psrvs:
                desc = tx(ps, "Desc")
                rev  = amt(ps, "TotalRevenueColumnAmt")
                ubi  = amt(ps, "UnrelatedBusinessRevenueAmt")
                rev_s = f"${rev:,}" if isinstance(rev, int) else str(rev)
                ubi_s = f"  (UBI: ${ubi:,})" if isinstance(ubi, int) and ubi else ""
                print(f"    {desc}: {rev_s}{ubi_s}")

        # ── Schedule L ────────────────────────────────────────────────────────
        schedl = data.find(f"{NS}IRS990ScheduleL") if data is not None else None
        if schedl is not None:
            txns = schedl.findall(f".//{NS}TransactionsRelatedOrgGrp")
            if txns:
                print("\n  SCHEDULE L - RELATED PARTY TRANSACTIONS")
                for txn in txns:
                    nm   = tx(txn, "NameOfInterested")
                    rel  = tx(txn, "RelationshipWithOrganizationTxt")
                    desc = tx(txn, "Desc")
                    a    = tx(txn, "TransactionAmt")
                    print(f"    {nm} | {rel} | {desc} | ${a}")

            loans = schedl.findall(f".//{NS}LoansBtwnOrgAndInterestedPrsnGrp")
            if loans:
                print("\n  SCHEDULE L - LOANS")
                for ln in loans:
                    nm   = tx(ln, "NameOfInterested")
                    rel  = tx(ln, "RelationshipWithOrganizationTxt")
                    bal  = tx(ln, "LoanBalanceEndOfYearAmt")
                    print(f"    {nm} | {rel} | balance: ${bal}")

        # ── Schedule R ────────────────────────────────────────────────────────
        schedr = data.find(f"{NS}IRS990ScheduleR") if data is not None else None
        if schedr is not None:
            exempt = schedr.findall(f".//{NS}IdRelatedTaxExemptOrgGrp")
            taxbl  = schedr.findall(f".//{NS}IdRelatedOrgTxblPartnershipGrp")
            corps  = schedr.findall(f".//{NS}IdRelatedOrgTxblCorpTrGrp")
            if exempt or taxbl or corps:
                print("\n  SCHEDULE R - RELATED ORGANIZATIONS")
                for rorg in exempt:
                    nm  = tx(rorg, "OrganizationNm") or tx(rorg, "BusinessName.BusinessNameLine1Txt")
                    ein = tx(rorg, "EIN")
                    act = tx(rorg, "PrimaryActivitiesTxt")
                    print(f"    [EXEMPT]  {nm}  EIN:{ein}  {act}")
                for rorg in taxbl:
                    nm  = tx(rorg, "OrganizationNm") or tx(rorg, "BusinessName.BusinessNameLine1Txt")
                    ein = tx(rorg, "EIN")
                    print(f"    [PARTNER] {nm}  EIN:{ein}")
                for rorg in corps:
                    nm  = tx(rorg, "OrganizationNm") or tx(rorg, "BusinessName.BusinessNameLine1Txt")
                    ein = tx(rorg, "EIN")
                    print(f"    [CORP]    {nm}  EIN:{ein}")

        # ── Schedule O ────────────────────────────────────────────────────────
        schedo = data.find(f"{NS}IRS990ScheduleO") if data is not None else None
        if schedo is not None:
            details = schedo.findall(f"{NS}SupplementalInformationDetail")
            if details:
                print("\n  SCHEDULE O - SUPPLEMENTAL INFORMATION")
                for d in details:
                    ref  = tx(d, "FormAndLineReferenceDesc")
                    expl = tx(d, "ExplanationTxt")
                    print(f"    [{ref}] {expl[:120]}")

    elif f990t is not None:
        print("\n  [990T - Unrelated Business Income Tax Return]")
        ubi_amt = amt(f990t, "GrossUBIAmt")
        if ubi_amt:
            print(f"  Gross UBI: ${ubi_amt:,}")

    print()


if __name__ == "__main__":
    xml_dir = Path(__file__).parent.parent / "private" / "example documents" / "990_xml"
    files = sorted(xml_dir.glob("*.xml"))
    print(f"Parsing {len(files)} files from {xml_dir}\n")
    for fpath in files:
        parse_file(str(fpath))
