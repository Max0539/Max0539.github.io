import pandas as pd
import io
from datetime import datetime

AKTUELLES_JAHR = datetime.now().year


def lade_und_filtere(pfad: str) -> pd.DataFrame:
    df = pd.read_csv(pfad, sep=";")
    if "Geschäftsjahr" in df.columns:
        df = df[df["Geschäftsjahr"].astype(str).str.contains(str(AKTUELLES_JAHR))]
    return df


bilanz = lade_und_filtere("bilanz.csv")
guv    = lade_und_filtere("guv.csv")

print(f"=== Bilanz {AKTUELLES_JAHR} ===")
print(bilanz.to_string(index=False))
print(f"\n=== GuV {AKTUELLES_JAHR} ===")
print(guv.to_string(index=False))


