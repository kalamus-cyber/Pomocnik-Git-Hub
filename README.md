# Pomocnik GitHub — Kubuntu / Ubuntu / Fedora

Prosta aplikacja okienkowa **po polsku** do obsługi projektów GitHub na Linuksie. Jest przeznaczona dla osób, które wolą klikać niż zapamiętywać polecenia Git. Współpracuje z edytorem **Kate**; przydaje się także przy projektach **FreeCAD**.

Program jest niezależnym projektem społecznościowym, **nie jest oficjalną aplikacją GitHub**.

## Funkcje

- **Pobierz nowy** — klonowanie projektu z GitHuba do wybranego katalogu.
- **Wyślij nowy** — połączenie katalogu z *uprzednio utworzonym pustym repozytorium* na GitHubie, wybór plików, Commit i Push.
- **Synchronizuj** — pobranie zmian (Pull) albo zatwierdzenie i wysłanie zmian (Commit + Push).
- **Otwórz w Kate** — uruchamia edytor dla wybranego projektu.

Program pokazuje wybrane pliki przed zatwierdzeniem, ostrzega przed typowymi plikami poufnymi oraz kopiami zapasowymi FreeCAD i nie stosuje `push --force`, `reset --hard` ani automatycznych scaleń. **To nie zastępuje samodzielnej kontroli plików** — przed upublicznieniem repozytorium sprawdź wszystkie pliki i historię Git.

## Wymagania

- Linux z działającym środowiskiem graficznym (sprawdzany na Kubuntu/Ubuntu; możliwe użycie na Fedorze)
- Python 3 i moduł `tkinter`
- Git
- Kate — opcjonalnie, dla przycisku „Otwórz w Kate”

Na Kubuntu/Ubuntu, gdy brakuje zależności:

```bash
sudo apt install git python3 python3-tk
```

Na Fedorze:

```bash
sudo dnf install git python3 python3-tkinter
```

## Instalacja

1. Pobierz pliki projektu (jako ZIP poprzez **Code → Download ZIP** lub przez Git).
2. Rozpakuj paczkę i otwórz terminal **w katalogu z plikiem `install.sh`**.
3. Uruchom:

```bash
bash install.sh
```

Instalacja jest lokalna, bez `sudo`, w katalogu `~/.local/`. Potem w menu aplikacji wyszukaj **Pomocnik GitHub**.

Aktualizacja: uruchom instalator z nowszej wersji — projekty Git nie są usuwane.

Odinstalowanie:

```bash
bash uninstall.sh
```

Skrypt usuwa tylko aplikację, nie katalogi z projektami.

## Pierwszy projekt na GitHubie

1. W witrynie GitHub utwórz nowe **puste** repozytorium (bez README, `.gitignore` i licencji).
2. Otwórz zakładkę **Wyślij nowy**.
3. Wskaż katalog projektu, wklej adres repozytorium, wybierz pliki, zatwierdź i wyślij.

Późniejsze użycie: przed pracą **Pobierz zmiany**, po pracy **Zatwierdź i wyślij**.

Przy istniejącym repozytorium z inną historią Git program nie nadpisze jej automatycznie — konflikty należy rozwiązać osobno.

## Bezpieczeństwo i ograniczenia

- Program nie tworzy repozytorium przez API GitHub. Robisz to samodzielnie w przeglądarce.
- Uwierzytelnianie Git używa istniejącej konfiguracji Git lub pomocniczego okienka; aplikacja sama nie przechowuje tokenów.
- Nie przechowuj tokenów, kluczy ani haseł w folderach udostępnianych jako repozytoria.
- Wcześniej dodane do indeksu pliki są także objęte Commit — sprawdź listę przed potwierdzeniem.
- Nie obsługuje Git LFS ani automatycznego rozwiązywania konfliktów.

Więcej informacji w pliku [`PRZECZYTAJ.txt`](PRZECZYTAJ.txt).

## Licencja

Kod programu jest dostępny na licencji **MIT** — patrz [`LICENSE`](LICENSE).

Wersja: **1.1** (10.11.2026).
