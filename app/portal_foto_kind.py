"""Kindprozess: ein Foto für das Kundenportal neu kodieren (seit 1.11.33, Stufe P2b; Bauplan P2, B5, Nachtrag 4).

Läuft nur als eigener Prozess, gestartet von app/portal_kopien.py::foto_neu_kodieren() mit `python -I <diese Datei> <Speicher> <Pixel> <Kante> <Qualität>`:
liest das Bild von stdin, schreibt das JPEG nach stdout, nichts sonst. Importiert nur die Standardbibliothek und Pillow -- nichts aus dem ERP (mit -I liegt
das Projekt gar nicht im Suchpfad), keine Umgebung (der Aufrufer gibt nur PATH weiter, keine Geheimnisse).

Zuerst setzt der Prozess seine eigene Grenze für Speicher: unter Linux RLIMIT_AS, unter Windows (nur Entwicklung und Tests) ein Job-Objekt mit
ProcessMemoryLimit. Danach: nur JPEG, PNG, WebP, GIF (Image.open(formats=…)); mehr als <Pixel> Bildpunkte -> Rückgabe 11; Drehung aus EXIF angewandt, nach
sRGB umgerechnet, wenn ein Farbprofil dabei ist (sonst unverändert), Transparenz auf Weiß, nur das erste Bild einer Animation, längste Kante <Kante>,
JPEG mit <Qualität> -- aus einem frischen Bild ohne jede Angabe (kein EXIF, XMP, IPTC, ICC, Kommentar; ein angehängter Rest der Datei geht verloren).

Rückgabe: 0 = JPEG auf stdout; 10 = nicht lesbar; 11 = zu groß (Bildpunkte); 12 = Speicher erschöpft. Jede andere (auch ein Absturz oder ein
Abbruch durch den Aufrufer nach der Zeitgrenze) heißt dort „abbruch“. stderr bleibt leer -- keine Meldung trägt Inhalt oder Metadaten des Bildes.
"""

import io
import sys
import warnings

OK, NICHT_LESBAR, ZU_GROSS, SPEICHER = 0, 10, 11, 12
FORMATE = ("JPEG", "PNG", "WEBP", "GIF")
# EXIF-Orientierung -> Drehung (wie PIL.ImageOps.exif_transpose)
DREHUNG = {2: "FLIP_LEFT_RIGHT", 3: "ROTATE_180", 4: "FLIP_TOP_BOTTOM", 5: "TRANSPOSE", 6: "ROTATE_270", 7: "TRANSVERSE", 8: "ROTATE_90"}


def speicher_begrenzen(grenze: int) -> None:
    """Die Grenze gilt für diesen Prozess, bevor er ein Byte des Bildes liest."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Basis(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

        class Zaehler(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("Read", "Write", "Other", "ReadBytes", "WriteBytes", "OtherBytes")]

        class Erweitert(ctypes.Structure):
            _fields_ = [("Basis", Basis), ("Io", Zaehler), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        job = k32.CreateJobObjectW(None, None)
        info = Erweitert()
        info.Basis.LimitFlags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = grenze
        if not job or not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)) \
                or not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):  # 9 = JobObjectExtendedLimitInformation
            raise OSError("Grenze für Speicher nicht gesetzt")
    else:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (grenze, grenze))


def neu_kodieren(daten: bytes, pixel: int, kante: int, qualitaet: int) -> bytes:
    from PIL import Image, ImageCms

    Image.MAX_IMAGE_PIXELS = pixel
    warnings.simplefilter("error", Image.DecompressionBombWarning)  # schon über der Grenze ist zu groß, nicht erst über dem Doppelten
    bild = Image.open(io.BytesIO(daten), formats=FORMATE)
    if bild.width * bild.height > pixel:
        raise Image.DecompressionBombError("zu groß")
    drehung = bild.getexif().get(0x0112, 1)
    profil = bild.info.get("icc_profile")
    bild.seek(0)
    bild.thumbnail((kante, kante))  # JPEG verkleinert schon beim Dekodieren (draft); lädt das Bild
    if drehung in DREHUNG:
        bild = bild.transpose(getattr(Image.Transpose, DREHUNG[drehung]))
    if bild.mode in ("RGBA", "LA", "PA") or (bild.mode == "P" and "transparency" in bild.info):
        rgba = bild.convert("RGBA")
        bild = Image.new("RGB", rgba.size, "white")
        bild.paste(rgba, mask=rgba.getchannel("A"))
    if profil and bild.mode in ("RGB", "L", "CMYK"):
        try:
            bild = ImageCms.profileToProfile(bild, ImageCms.ImageCmsProfile(io.BytesIO(profil)), ImageCms.createProfile("sRGB"), outputMode="RGB")
        except (ImageCms.PyCMSError, OSError, ValueError, TypeError):
            pass  # ein kaputtes Profil: die Farben bleiben, wie sie sind
    bild = bild.convert("RGB")
    sauber = Image.new("RGB", bild.size)  # ein frisches Bild: keine Angabe aus der Datei kommt mit
    sauber.paste(bild)
    aus = io.BytesIO()
    sauber.save(aus, "JPEG", quality=qualitaet, optimize=True)
    return aus.getvalue()


def main(argv: list[str]) -> int:
    try:
        speicher, pixel, kante, qualitaet = (int(x) for x in argv[1:5])
    except (ValueError, TypeError):
        return 2
    speicher_begrenzen(speicher)
    daten = sys.stdin.buffer.read()
    try:
        from PIL import Image
        try:
            jpeg = neu_kodieren(daten, pixel, kante, qualitaet)
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            return ZU_GROSS
    except MemoryError:
        return SPEICHER
    except Exception:  # noqa: BLE001 -- jedes andere Problem mit dem Inhalt: nicht lesbar (ohne Text, er könnte aus der Datei stammen)
        return NICHT_LESBAR
    sys.stdout.buffer.write(jpeg)
    sys.stdout.buffer.flush()
    return OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
