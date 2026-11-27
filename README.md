# mytool

## Ne yapar

Bu bir komut satırı aracıdır: önce statik analiz (ruff) gerçek bulguları çıkarır, sonra LLM yalnızca bu bulgular için yama önerir, en sonda her öneri geçici bir kopyada doğrulanır (sözdizimi, ruff, projenin testleri). Doğrulamada başarısız olan öneri hiç gösterilmez; doğrulanamayan öneri (ör. projede test yok) `⚠` ile işaretlenir ve `--fix` ile otomatik uygulanmaz. Ayrıca `optimize` (cProfile ile ölçülmüş hızlanma), `shrink` (daha kısa eşdeğer kod), `translate` (başka dile çeviri) ve `explain` (Türkçe açıklama) komutları vardır. Bugün yalnızca Python desteklenir.

## Kurulum

Python 3.11+ gerekir.

```bash
uv tool install .          # depo dizininden; ardından: mytool --help
# ya da geliştirme için:
uv sync
uv run mytool --help
```

Ortam değişkenleri:

- `ANTHROPIC_API_KEY`: LLM kullanan komutlar için gerekli (`--static` olmadan `analyze`, ayrıca `optimize`, `shrink`, `translate`, `explain`). Yoksa `analyze` yalnız statik bulguları gösterir, diğerleri çıkış kodu 2 ile durur.
- `MYTOOL_MODEL`: kullanılacak model (varsayılan `claude-sonnet-5-5`). `--model` bunu ezer.
- `MYTOOL_DEBUG=1`: beklenmeyen hatalarda ayrıntılı traceback gösterir.

## Hızlı başlangıç

```bash
# Statik analiz, LLM yok (API anahtarı gerekmez)
mytool analyze src/ --static

# Analiz + doğrulanmış yama önerileri; etkileşimli uygulama sorusu çıkar
mytool analyze app.py

# Yalnız diff göster / doğrulanmışları otomatik uygula / JSON çıktı
mytool analyze app.py --diff
mytool analyze app.py --fix
mytool analyze app.py --json

# Son uygulamayı geri al
mytool undo
mytool undo --yes

# cProfile ile ölçülmüş hızlanma; --bench iş yükünü veren betiktir
mytool optimize calc.py --bench bench.py

# En uzun işlevler için daha kısa kod
mytool shrink calc.py

# Başka dile çeviri; --out yeni dosyaya yazar
mytool translate app.py --to javascript --out app.js

# Dosyanın ne yaptığını Türkçe anlat
mytool explain app.py
```

## Gizlilik ve güvenlik

**Okumadan kullanma.**

- **Kod Anthropic API'ye gönderilir.** Depo bütünü gönderilmez; yalnızca ilgili işlev (veya bulgunun çevresindeki yaklaşık 15 satırlık pencere) gider. İstisnalar: `explain` 400 satıra kadar dosyaları bütün olarak gönderir (daha büyük dosyalarda işlev işlev), `translate` dosyayı parça parça gönderir. Her komut göndermeden önce bir not yazar. `--static` hiçbir şey göndermez.
- **Deny-list.** Adı şu desenlerden birine uyan dosyalar hiç okunup gönderilmez: `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa*`, `*secret*`, `*credentials*`, `*.p12`.
- **Doğrulama ve optimize kodunu bu makinede çalıştırır.** Yama doğrulaması projenin testlerini (`pytest`), `optimize` ise benchmark betiğini, testleri veya dosyanın kendisini geçici bir proje kopyasında çalıştırır. **Sandbox yoktur**: kod senin kullanıcı yetkinle çalışır. Ortam değişkenlerinden adında `SECRET`, `TOKEN`, `PASSWORD`, `API_KEY` geçenler ve `ANTHROPIC_API_KEY` ayıklanır; her çalıştırmada zaman aşımı vardır (`--timeout`, varsayılan 60 sn). Güvenmediğin projede çalıştırma. `translate` de hedef derleyiciyi/denetleyiciyi (ve JavaScript için orijinal betiği) aynı şekilde çalıştırır.
- **`--no-verify`** yama doğrulamasını atlar; böyle öneriler `--fix` ile uygulanmaz. `optimize` yine de iş yükünü çalıştırır (profil için).
- **Yedek ve geri alma.** Uygulanan her yama önce `.mytool/backup/<zaman>/` altına yedeklenir; `mytool undo` son yedeği geri yükler. `.mytool/` dizinini `.gitignore` dosyana ekle.

## Komutlar ve bayraklar

| Komut | Ne yapar | Bayraklar |
| --- | --- | --- |
| `analyze <yol>` | Statik analiz + doğrulanmış yama önerisi (dosya veya dizin) | `--diff`, `--fix`, `--json`, `--no-verify`, `--model`, `--max-findings`, `--max-tokens`, `--static`, `--timeout`, `--verbose` |
| `optimize <dosya>` | cProfile ile profil, ölçülmüş hızlanma | `--bench`, `--diff`, `--fix`, `--json`, `--no-verify`, `--model`, `--max-tokens`, `--timeout`, `--verbose` |
| `shrink <dosya>` | En uzun işlevler için daha kısa eşdeğer kod | `--diff`, `--fix`, `--json`, `--no-verify`, `--model`, `--max-findings`, `--max-tokens`, `--timeout`, `--verbose` |
| `translate <dosya>` | İşlev işlev başka dile çeviri | `--to` (zorunlu), `--out`, `--force`, `--json`, `--no-verify`, `--model`, `--max-tokens`, `--timeout`, `--verbose` |
| `explain <dosya>` | Dosyanın ne yaptığını Türkçe açıklar | `--json`, `--model`, `--max-tokens`, `--verbose` |
| `undo [dizin]` | Son yedeği geri yükler | `--yes` |

Bayrakların anlamı her komutta aynıdır:

| Bayrak | Anlam |
| --- | --- |
| `--diff` | Yamaları birleşik diff olarak göster |
| `--fix` | Doğrulanmış yamaları uygula (yedek alınır) |
| `--json` | Makine okunur JSON (notlar stderr'e gider) |
| `--no-verify` | Doğrulamayı atla |
| `--model` | Model adı (`MYTOOL_MODEL`'i ezer) |
| `--max-findings` | LLM'e gönderilecek en çok bulgu / işlev sayısı |
| `--max-tokens` | İstek başına en çok çıkış tokeni |
| `--static` | LLM'siz, yalnız statik bulgular |
| `--timeout` | Alt süreç zaman aşımı, saniye |
| `--verbose` | Ayrıntı; token ve tahmini maliyet satırı |
| `--bench` | `optimize` için iş yükü betiği (proje içinde olmalı) |
| `--to` | `translate` hedef dili: `javascript`, `typescript`, `c`, `cpp`, `go`, `rust`, `java` ya da başka bir ad |
| `--out` | Çeviriyi bu yeni dosyaya yaz (kaynağın yanına varsayılan olarak yazılmaz) |
| `--force` | Var olan `--out` dosyasının üzerine yaz (eskisi yedeklenir) |
| `--yes` | `undo` onay sormasın |

`--verbose` token satırı: `Token: giriş X, çıkış Y — tahmini maliyet $0.0123`. Fiyat tablosu `mytool/core/pricing.py` içinde bir anlık görüntüdür, güncel olmayabilir; bilinmeyen modelde maliyet hesaplanmaz.

## Çıkış kodları

| Kod | Anlam |
| --- | --- |
| 0 | Başarılı (uyarılar ve bulgular hata sayılmaz) |
| 1 | Beklenmeyen hata; ya da `undo` için geri alınacak yedek yok |
| 2 | Kullanım/girdi hatası: yol yok, dizin yerine dosya beklendi, eksik `ANTHROPIC_API_KEY`, geçersiz bayrak, okunamayan dosya, etkileşimsiz ortamda `undo` için `--yes` yok |
| 3 | Araç veya LLM hatası (ruff çalışmadı, API hatası, desteklenmeyen dil/deny-list, doğrulamada başarısız çeviri) |
| 130 | Ctrl+C ile iptal |

## Doğrulama nasıl çalışır

Her yama, gerçek dosyaya dokunmadan geçici bir proje kopyasında sırayla denenir:

1. Yama kopyaya uygulanır (eşleşmezse öneri düşer).
2. Sözdizimi denetimi.
3. ruff: yamadan önce olmayan yeni bir hata çıkarsa öneri düşer.
4. pytest: önce yamasız kopyada bir kez çalıştırılır (baseline); geçmiyorsa testler güvenilmez sayılır. Geçiyorsa yamalı kopyada tekrar çalışır.

Sonuç etiketleri:

- `✓ testler geçti`: sözdizimi, ruff ve testler geçti. `--fix` yalnız bunları (ve ölçülmüş optimize önerilerini) uygular.
- `⚠ doğrulanamadı (yalnız sözdizimi: ...)`: test yok, test baseline'ı geçmiyor veya proje çok büyük; yalnız sözdizimi denetlendi. Etkileşimli seçimle uygulanabilir, `--fix` uygulamaz.
- `⚠ doğrulanmadı (--no-verify)` ve `⚠ yalnız açıklama`: doğrulama yapılmadı veya yama yok.
- Doğrulamada başarısız öneriler gizlenir; kaç tane gizlendiği yazılır, nedeni `--verbose` ile görünür.

`optimize` ek olarak iş yükünü (`--bench` betiği, yoksa projenin testleri, yoksa `__main__` korumalı dosyanın kendisi) yamadan önce ve sonra 3 kez ölçer. Kurallar: iş yükünün çıktısı birebir aynı kalmalı ve medyan süre en az %5 (`1.05x`) hızlanmalı; aksi halde öneri düşer.

`translate`: çıktı hedef aracın denetleyicisinden geçirilir (javascript için `node --check`, c/cpp için `-fsyntax-only`, go için `gofmt -e`, rust için `rustc`, java için `javac`). Karşılaştırma yalnız javascript için ve kaynakta `if __name__ == "__main__":` varsa yapılır: orijinal betik ile çevirinin çıktısı aynı olmalıdır. Bilinmeyen hedef veya araç yoksa doğrulama atlanır ve `⚠` gösterilir. Doğrulamada başarısız çeviri kod olarak gösterilmez ve `--out` dosyasına yazılmaz.

## Mimari

```
        cli/ (main.py, render.py, interact.py)    Typer + Rich, yalnız arayüz
                      |
                      v
              core/pipeline.py  ----------------------------+
              |      |       |        |         |           |
              v      v       v        v         v           v
        analyzers/  languages/  llm.py   verify.py   translate.py   apply.py
        (ruff)      (python)    prompts  profiling.py               patching.py
              \         |         |          |            |            /
               +--------+---- models.py (paylaşılan pydantic modelleri) ---+
```

**core'da UI yok**: `core/` içinde `print`, `input`, `rich` ve `typer` kullanılmaz (bunu `tests/test_core_purity.py` denetler). Core veri döndürür, `cli/` biçimlendirir. Böylece aynı çekirdek ileride bir LSP sunucusu veya web arayüzü tarafından olduğu gibi yeniden kullanılabilir.

## Yeni dil ekleme rehberi

Dil eklentisi `mytool/core/languages/base.py` içindeki `LanguagePlugin` protokolüdür: `name`, `extensions`, `extract_units(source)` ve `check_syntax(source, filename)`.

1. Tree-sitter dil paketini `pyproject.toml` bağımlılıklarına ekle (ör. `tree-sitter-javascript`).
2. `mytool/core/languages/javascript.py` oluştur:

```python
import tree_sitter_javascript
from tree_sitter import Language, Parser

from mytool.core.models import CodeUnit, LineRange, UnitKind


class JavaScriptPlugin:
    name = "javascript"
    extensions: tuple[str, ...] = (".js",)

    def __init__(self) -> None:
        self._parser = Parser(Language(tree_sitter_javascript.language()))

    def extract_units(self, source: str) -> list[CodeUnit]:
        tree = self._parser.parse(source.encode("utf-8"))
        units: list[CodeUnit] = []
        # tree.root_node içinde işlev/sınıf düğümlerini gez; her biri için:
        # units.append(CodeUnit(name=..., kind=UnitKind.FUNCTION,
        #                       lines=LineRange(start=..., end=...), source=...))
        return units

    def check_syntax(self, source: str, filename: str) -> str | None:
        """Hata mesajı döndür; sözdizimi temizse None."""
        return None
```

3. `mytool/core/languages/__init__.py` içindeki `_PLUGINS` demetine ekle: `_PLUGINS = (PythonPlugin(), JavaScriptPlugin())`. `plugin_for(path)` uzantıya göre seçer.
4. Birim testi yaz (`tests/test_python_plugin.py` örnek). Not: analyzer'lar (aşağıda) dile bağlıdır; yeni dil için uygun bir analyzer de gerekir, aksi halde bulgu çıkmaz.

## Yeni analyzer ekleme rehberi

Analyzer, `mytool/core/analyzers/base.py` içindeki `Analyzer` protokolüdür: `name`, `languages` (eklenti adları) ve `run(files, timeout_s) -> list[Finding]`. Başarısızlıkta kullanıcıya gösterilecek mesajla `AnalyzerError` fırlat; pipeline bunu çıkış kodu 3'e çevirir.

```python
from pathlib import Path

from mytool.core.analyzers.base import AnalyzerError
from mytool.core.models import Category, Finding, LineRange, Severity


class MyAnalyzer:
    name = "myanalyzer"
    languages: tuple[str, ...] = ("python",)

    def run(self, files: list[Path], timeout_s: float) -> list[Finding]:
        try:
            raw = run_my_tool(files, timeout_s)  # alt süreç vb.
        except OSError as exc:
            raise AnalyzerError(f"myanalyzer çalışmadı: {exc}") from exc
        return [
            Finding(
                id=f"my-{item.id}",
                tool=self.name,
                file=Path(item.path),
                lines=LineRange(start=item.line, end=item.line),
                severity=Severity.WARNING,  # ERROR / WARNING / INFO
                rule=item.code,
                message=item.message,
                category=Category.BUG,  # BUG / SECURITY / PERF / STYLE
            )
        ]
```

Kural kodunu `severity` ve `category` değerlerine eşleyen küçük işlevler yaz (ruff için `severity_for` ve `category_for`, `mytool/core/analyzers/ruff.py`). Kayıt noktası: `mytool/core/pipeline.py` içindeki `analyze_static`; analyzer verilmezse `[RuffAnalyzer()]` kullanılır, yenisini bu listeye ekle. Test için `analyze(path, cfg, llm, [MyAnalyzer()])` ile doğrudan verilebilir (`tests/test_cli.py` içindeki `Failing` örneğine bak).

## Bilinen sınırlar

- Yalnız Python kaynak dili desteklenir.
- Her yama için tüm test paketi yeniden çalışır; büyük projelerde yavaştır (proje çok büyükse testler atlanır, yalnız sözdizimi denetlenir).
- Sandbox yoktur; doğrulama ve optimize kodu bu makinede çalıştırır.
- Karışık satır sonları yama uygulanırken CRLF'e normalleşir.
- `translate` çıktı karşılaştırması yalnız javascript hedefi için vardır; diğer hedeflerde yalnız sözdizimi denetimi yapılır.
- Gerçek LLM yolu test paketinde yalnızca sahte (mock) istemciyle sınanmıştır.
- `--help` içindeki bazı sabit ifadeler (ör. "Show this message and exit.") ve Typer'ın kullanım hatası iletileri İngilizce kalır.

## Geliştirme

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy mytool tests
```

Paket derlemesi: `uv build` (çıktı `dist/` altına gider, depoya eklenmez).
