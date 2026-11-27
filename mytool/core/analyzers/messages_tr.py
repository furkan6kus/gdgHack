"""Turkish messages for the ruff rules mytool enables (E4, E7, E9, F, B, S, PERF, SIM).

Each rule maps to ``(english_format, turkish_format)`` pairs. The English side is
ruff's own message format (``ruff rule --all --output-format json``); its
``{placeholders}`` are matched against the real message and reused in the
Turkish text. When ruff changes a wording, the rule still gets a Turkish
message (the first Turkish variant, placeholders shown as "…"); a rule missing
from this table keeps ruff's English text.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import cache

_XML = (
    "Using `xml` to parse untrusted data is known to be vulnerable to XML attacks; "
    "use `defusedxml` equivalents",
    "Güvenilmeyen veriyi `xml` ile ayrıştırmak XML saldırılarına açıktır; "
    "`defusedxml` karşılıklarını kullanın",
)

_DEFAULT_ARG = (
    "Do not perform function call `{name}` in argument defaults; instead, perform the call "
    "within the function, or read the default from a module-level singleton variable"
)

_RAISE_FROM = (
    "raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them "
    "from errors in exception handling"
)
_RAISE_FROM_TR = (
    "hata işleme sırasında çıkan hatalardan ayırmak için `raise ... from err` ya da "
    "`raise ... from None` kullanın"
)

MESSAGES: dict[str, tuple[tuple[str, str], ...]] = {
    # --- güvenlik (bandit, S) ---
    "S101": (("Use of `assert` detected", "`assert` kullanılmış (python -O ile kaldırılır)"),),
    "S102": (("Use of `exec` detected", "`exec` kullanılmış"),),
    "S103": (
        (
            "`os.chmod` setting a permissive mask `{mask}` on file or directory",
            "`os.chmod` dosya ya da klasöre fazla geniş izin (`{mask}`) veriyor",
        ),
        (
            "`os.chmod` setting an invalid mask on file or directory",
            "`os.chmod` dosya ya da klasöre geçersiz bir izin maskesi veriyor",
        ),
    ),
    "S104": (("Possible binding to all interfaces", "Tüm ağ arayüzlerine bağlanılıyor olabilir"),),
    "S105": (
        (
            'Possible hardcoded password assigned to: "{arg0}"',
            'Koda gömülü parola olabilir: "{arg0}"',
        ),
    ),
    "S106": (
        (
            'Possible hardcoded password assigned to argument: "{arg0}"',
            'Argümana koda gömülü parola verilmiş olabilir: "{arg0}"',
        ),
    ),
    "S107": (
        (
            'Possible hardcoded password assigned to function default: "{arg0}"',
            'Fonksiyonun varsayılan değeri koda gömülü bir parola olabilir: "{arg0}"',
        ),
    ),
    "S108": (
        (
            'Probable insecure usage of temporary file or directory: "{arg0}"',
            'Geçici dosya ya da klasör güvensiz kullanılıyor olabilir: "{arg0}"',
        ),
    ),
    "S110": (
        (
            "`try`-`except`-`pass` detected, consider logging the exception",
            "`try`-`except`-`pass` hatayı sessizce yutuyor; hatayı kaydetmeyi düşünün",
        ),
    ),
    "S112": (
        (
            "`try`-`except`-`continue` detected, consider logging the exception",
            "`try`-`except`-`continue` hatayı sessizce yutuyor; hatayı kaydetmeyi düşünün",
        ),
    ),
    "S113": (
        (
            "Probable use of `{module}` call without timeout",
            "`{module}` çağrısında zaman aşımı (timeout) yok; istek sonsuza kadar bekleyebilir",
        ),
        (
            "Probable use of `{module}` call with timeout set to `None`",
            "`{module}` çağrısında zaman aşımı `None`; istek sonsuza kadar bekleyebilir",
        ),
    ),
    "S201": (
        (
            "Use of `debug=True` in Flask app detected",
            "Flask uygulamasında `debug=True` kullanılmış; canlı ortamda kod çalıştırmaya açar",
        ),
    ),
    "S202": (
        ("Uses of `tarfile.extractall()`", "`tarfile.extractall()` güvensiz (yol aşımı riski)"),
    ),
    "S301": (
        (
            "`pickle` and modules that wrap it can be unsafe when used to deserialize untrusted "
            "data, possible security issue",
            "`pickle` ile güvenilmeyen veri açmak güvensizdir; olası güvenlik açığı",
        ),
    ),
    "S302": (
        (
            "Deserialization with the `marshal` module is possibly dangerous",
            "`marshal` modülüyle veri açmak tehlikeli olabilir",
        ),
    ),
    "S303": (
        (
            "Use of insecure MD2, MD4, MD5, or SHA1 hash function",
            "Güvensiz özet fonksiyonu (MD2, MD4, MD5 ya da SHA1) kullanılmış",
        ),
    ),
    "S304": (
        (
            "Use of insecure cipher, replace with a known secure cipher such as AES",
            "Güvensiz şifreleme algoritması; AES gibi güvenli bir algoritma kullanın",
        ),
    ),
    "S305": (
        (
            "Use of insecure block cipher mode, replace with a known secure mode "
            "such as CBC or CTR",
            "Güvensiz blok şifre kipi; CBC ya da CTR gibi güvenli bir kip kullanın",
        ),
    ),
    "S306": (
        (
            "Use of insecure and deprecated function (`mktemp`)",
            "Güvensiz ve eskimiş `mktemp` fonksiyonu kullanılmış",
        ),
    ),
    "S307": (
        (
            "Use of possibly insecure function; consider using `ast.literal_eval`",
            "Güvensiz olabilecek fonksiyon (`eval`); `ast.literal_eval` kullanmayı düşünün",
        ),
    ),
    "S308": (
        (
            "Use of `mark_safe` may expose cross-site scripting vulnerabilities",
            "`mark_safe` kullanımı XSS (siteler arası betik) açığına yol açabilir",
        ),
    ),
    "S310": (
        (
            "Audit URL open for permitted schemes. Allowing use of `file:` or custom schemes is "
            "often unexpected.",
            "Açılan URL'nin şemasını denetleyin; `file:` ya da özel şemalara izin vermek "
            "çoğu zaman istenmeyen bir durumdur",
        ),
    ),
    "S311": (
        (
            "Standard pseudo-random generators are not suitable for cryptographic purposes",
            "Standart rastgele sayı üreteçleri şifreleme amaçları için uygun değil; "
            "`secrets` modülünü kullanın",
        ),
    ),
    "S312": (
        (
            "Telnet is considered insecure. Use SSH or some other encrypted protocol.",
            "Telnet güvensizdir; SSH ya da şifreli başka bir protokol kullanın",
        ),
    ),
    "S313": (_XML,),
    "S314": (_XML,),
    "S315": (_XML,),
    "S316": (_XML,),
    "S317": (_XML,),
    "S318": (_XML,),
    "S319": (_XML,),
    "S321": (
        (
            "FTP-related functions are being called. FTP is considered insecure. Use SSH/SFTP/SCP "
            "or some other encrypted protocol.",
            "FTP fonksiyonları çağrılıyor; FTP güvensizdir, SSH/SFTP/SCP gibi şifreli bir "
            "protokol kullanın",
        ),
    ),
    "S323": (
        (
            "Python allows using an insecure context via the `_create_unverified_context` that "
            "reverts to the previous behavior that does not validate certificates or perform "
            "hostname checks.",
            "`_create_unverified_context` sertifika ve sunucu adı doğrulamasını kapatır; güvensiz",
        ),
    ),
    "S324": (
        (
            "Probable use of insecure hash functions in `{library}`: `{string}`",
            "`{library}` içinde güvensiz özet fonksiyonu kullanılıyor olabilir: `{string}`",
        ),
    ),
    "S501": (
        (
            "Probable use of `{string}` call with `verify=False` disabling SSL certificate checks",
            "`{string}` çağrısında `verify=False` SSL sertifika denetimini kapatıyor",
        ),
    ),
    "S502": (
        (
            "Call made with insecure SSL protocol: `{protocol}`",
            "Güvensiz SSL protokolüyle çağrı yapılmış: `{protocol}`",
        ),
    ),
    "S503": (
        (
            "Argument default set to insecure SSL protocol: `{protocol}`",
            "Argümanın varsayılanı güvensiz SSL protokolü: `{protocol}`",
        ),
    ),
    "S504": (
        (
            "`ssl.wrap_socket` called without an `ssl_version``",
            "`ssl.wrap_socket` `ssl_version` belirtilmeden çağrılmış",
        ),
    ),
    "S505": (
        (
            "{cryptographic_key} key sizes below {minimum_key_size} bits are considered breakable",
            "{minimum_key_size} bitten kısa {cryptographic_key} anahtarları kırılabilir sayılır",
        ),
    ),
    "S506": (
        (
            "Probable use of unsafe loader `{name}` with `yaml.load`. Allows instantiation of "
            "arbitrary objects. Consider `yaml.safe_load`.",
            "`yaml.load` güvensiz `{name}` yükleyicisiyle çağrılmış; rastgele nesne "
            "oluşturulabilir. `yaml.safe_load` kullanın",
        ),
        (
            "Probable use of unsafe `yaml.load`. Allows instantiation of arbitrary objects. "
            "Consider `yaml.safe_load`.",
            "Güvensiz `yaml.load` kullanımı; rastgele nesne oluşturulabilir. "
            "`yaml.safe_load` kullanın",
        ),
    ),
    "S507": (
        (
            "Paramiko call with policy set to automatically trust the unknown host key",
            "Paramiko bilinmeyen sunucu anahtarına otomatik güveniyor",
        ),
    ),
    "S508": (
        (
            "The use of SNMPv1 and SNMPv2 is insecure. Use SNMPv3 if able.",
            "SNMPv1 ve SNMPv2 güvensizdir; mümkünse SNMPv3 kullanın",
        ),
    ),
    "S509": (
        (
            "You should not use SNMPv3 without encryption. `noAuthNoPriv` & `authNoPriv` is "
            "insecure.",
            "SNMPv3 şifrelemesiz kullanılmamalı; `noAuthNoPriv` ve `authNoPriv` güvensizdir",
        ),
    ),
    "S601": (
        (
            "Possible shell injection via Paramiko call; check inputs are properly sanitized",
            "Paramiko çağrısında komut enjeksiyonu riski; girdilerin temizlendiğinden emin olun",
        ),
    ),
    "S602": (
        (
            "`subprocess` call with `shell=True` seems safe, but may be changed in the future; "
            "consider rewriting without `shell`",
            "`subprocess` çağrısında `shell=True` şimdilik güvenli görünüyor ama ileride "
            "değişebilir; `shell` olmadan yazmayı düşünün",
        ),
        (
            "`subprocess` call with `shell=True` identified, security issue",
            "`subprocess` çağrısında `shell=True` var; komut enjeksiyonu riski",
        ),
        (
            "`subprocess` call with truthy `shell` seems safe, but may be changed in the future; "
            "consider rewriting without `shell`",
            "`subprocess` çağrısında `shell` açık; şimdilik güvenli görünüyor ama ileride "
            "değişebilir, `shell` olmadan yazmayı düşünün",
        ),
        (
            "`subprocess` call with truthy `shell` identified, security issue",
            "`subprocess` çağrısında `shell` açık; komut enjeksiyonu riski",
        ),
    ),
    "S603": (
        (
            "`subprocess` call: check for execution of untrusted input",
            "`subprocess` çağrısı: güvenilmeyen girdinin çalıştırılmadığından emin olun",
        ),
    ),
    "S604": (
        (
            "Function call with `shell=True` parameter identified, security issue",
            "Fonksiyon `shell=True` ile çağrılmış; komut enjeksiyonu riski",
        ),
        (
            "Function call with truthy `shell` parameter identified, security issue",
            "Fonksiyon `shell` açık olarak çağrılmış; komut enjeksiyonu riski",
        ),
    ),
    "S605": (
        (
            "Starting a process with a shell: seems safe, but may be changed in the future; "
            "consider rewriting without `shell`",
            "Süreç kabuk (shell) üzerinden başlatılıyor; şimdilik güvenli görünüyor ama ileride "
            "değişebilir, kabuksuz yazmayı düşünün",
        ),
        (
            "Starting a process with a shell, possible injection detected",
            "Süreç kabuk (shell) üzerinden başlatılıyor; komut enjeksiyonu riski",
        ),
    ),
    "S606": (("Starting a process without a shell", "Süreç kabuk kullanılmadan başlatılıyor"),),
    "S607": (
        (
            "Starting a process with a partial executable path",
            "Süreç tam olmayan bir program yoluyla başlatılıyor",
        ),
    ),
    "S608": (
        (
            "Possible SQL injection vector through string-based query construction",
            "Sorgu metin birleştirerek kuruluyor; SQL enjeksiyonu riski",
        ),
    ),
    "S609": (
        (
            "Possible wildcard injection in call due to `*` usage",
            "`*` kullanımı nedeniyle joker karakter enjeksiyonu riski",
        ),
    ),
    "S610": (
        (
            "Use of Django `extra` can lead to SQL injection vulnerabilities",
            "Django `extra` kullanımı SQL enjeksiyonu açığına yol açabilir",
        ),
    ),
    "S611": (
        (
            "Use of `RawSQL` can lead to SQL injection vulnerabilities",
            "`RawSQL` kullanımı SQL enjeksiyonu açığına yol açabilir",
        ),
    ),
    "S612": (
        (
            "Use of insecure `logging.config.listen` detected",
            "Güvensiz `logging.config.listen` kullanılmış",
        ),
    ),
    "S701": (
        (
            "Using jinja2 templates with `autoescape=False` is dangerous and can lead to XSS. "
            "Ensure `autoescape=True` or use the `select_autoescape` function.",
            "jinja2 şablonlarında `autoescape=False` tehlikelidir (XSS); `autoescape=True` "
            "ya da `select_autoescape` kullanın",
        ),
        (
            "By default, jinja2 sets `autoescape` to `False`. Consider using `autoescape=True` "
            "or the `select_autoescape` function to mitigate XSS vulnerabilities.",
            "jinja2 varsayılan olarak `autoescape` kapalıdır; XSS'e karşı `autoescape=True` "
            "ya da `select_autoescape` kullanın",
        ),
    ),
    "S702": (
        (
            "Mako templates allow HTML and JavaScript rendering by default and are inherently "
            "open to XSS attacks",
            "Mako şablonları varsayılan olarak HTML ve JavaScript işler; XSS saldırılarına açıktır",
        ),
    ),
    "S704": (("Unsafe use of `{name}` detected", "`{name}` güvensiz biçimde kullanılmış"),),
    # --- olası hatalar (bugbear, B) ---
    "B002": (
        (
            "Python does not support the unary prefix increment operator (`++`)",
            "Python'da `++` artırma işleci yoktur; `x += 1` kullanın",
        ),
        (
            "Python does not support the unary prefix decrement operator (`--`)",
            "Python'da `--` azaltma işleci yoktur; `x -= 1` kullanın",
        ),
    ),
    "B003": (
        (
            "Assigning to `os.environ` doesn't clear the environment",
            "`os.environ`'a atama yapmak ortam değişkenlerini temizlemez",
        ),
    ),
    "B004": (
        (
            'Using `hasattr(x, "__call__")` to test if x is callable is unreliable. Use '
            "`callable(x)` for consistent results.",
            'Çağrılabilirliği `hasattr(x, "__call__")` ile denetlemek güvenilmez; '
            "`callable(x)` kullanın",
        ),
    ),
    "B005": (
        (
            "Using `.{strip}()` with multi-character strings is misleading",
            "`.{strip}()` birden çok karakterli metinle yanıltıcıdır (karakter kümesi olarak "
            "çalışır)",
        ),
        (
            "Using `.strip()` with multi-character strings is misleading",
            "`.strip()` birden çok karakterli metinle yanıltıcıdır (karakter kümesi olarak "
            "çalışır)",
        ),
    ),
    "B006": (
        (
            "Do not use mutable data structures for argument defaults",
            "Değiştirilebilir yapılar (liste, sözlük, küme) varsayılan argüman olmamalı; "
            "değer çağrılar arasında paylaşılır",
        ),
    ),
    "B007": (
        (
            "Loop control variable `{name}` not used within loop body",
            "Döngü değişkeni `{name}` döngü içinde kullanılmıyor",
        ),
        (
            "Loop control variable `{name}` may not be used within loop body",
            "Döngü değişkeni `{name}` döngü içinde kullanılmıyor olabilir",
        ),
    ),
    "B008": (
        (
            _DEFAULT_ARG,
            "Varsayılan argümanda `{name}` çağrılmamalı; çağrıyı fonksiyonun içinde yapın",
        ),
        (
            _DEFAULT_ARG.replace(" `{name}`", ""),
            "Varsayılan argümanda fonksiyon çağrılmamalı; çağrıyı fonksiyonun içinde yapın",
        ),
    ),
    "B009": (
        (
            "Do not call `getattr` with a constant attribute value. It is not any safer than "
            "normal property access.",
            "Sabit öznitelik adıyla `getattr` çağırmayın; normal erişimden daha güvenli değil",
        ),
    ),
    "B010": (
        (
            "Do not call `setattr` with a constant attribute value. It is not any safer than "
            "normal property access.",
            "Sabit öznitelik adıyla `setattr` çağırmayın; normal atamadan daha güvenli değil",
        ),
    ),
    "B011": (
        (
            "Do not `assert False` (`python -O` removes these calls), raise `AssertionError()`",
            "`assert False` kullanmayın (`python -O` bunu siler); `raise AssertionError()` yazın",
        ),
    ),
    "B012": (
        (
            "`{name}` inside `finally` blocks cause exceptions to be silenced",
            "`finally` içindeki `{name}` hataların sessizce kaybolmasına yol açar",
        ),
    ),
    "B013": (
        (
            "A length-one tuple literal is redundant in exception handlers",
            "Hata yakalayıcıda tek elemanlı demet gereksiz",
        ),
    ),
    "B014": (
        (
            "Exception handler with duplicate exception: `{name}`",
            "Hata yakalayıcıda tekrarlanan hata türü: `{name}`",
        ),
        (
            "Exception handler with duplicate exceptions: {names}",
            "Hata yakalayıcıda tekrarlanan hata türleri: {names}",
        ),
    ),
    "B015": (
        (
            "Pointless comparison. Did you mean to assign a value? Otherwise, prepend `assert` "
            "or remove it.",
            "Anlamsız karşılaştırma; atama mı yapmak istediniz? Değilse başına `assert` ekleyin "
            "ya da silin",
        ),
        (
            "Pointless comparison at end of function scope. Did you mean to return the "
            "expression result?",
            "Fonksiyon sonunda anlamsız karşılaştırma; sonucu döndürmek mi istediniz?",
        ),
    ),
    "B016": (
        (
            "Cannot raise a literal. Did you intend to return it or raise an Exception?",
            "Sabit bir değer `raise` edilemez; döndürmek mi yoksa bir Exception mı "
            "fırlatmak istediniz?",
        ),
    ),
    "B017": (
        (
            "Do not assert blind exception: `{exception}`",
            "Çok genel hata türü beklenmemeli: `{exception}`",
        ),
    ),
    "B018": (
        (
            "Found useless expression. Either assign it to a variable or remove it.",
            "İşe yaramayan ifade; bir değişkene atayın ya da silin",
        ),
        (
            "Found useless attribute access. Either assign it to a variable or remove it.",
            "İşe yaramayan öznitelik erişimi; bir değişkene atayın ya da silin",
        ),
    ),
    "B019": (
        (
            "Use of `functools.lru_cache` or `functools.cache` on methods can lead to memory leaks",
            "Metotlarda `functools.lru_cache` ya da `functools.cache` bellek sızıntısına yol "
            "açabilir",
        ),
    ),
    "B020": (
        (
            "Loop control variable `{name}` overrides iterable it iterates",
            "Döngü değişkeni `{name}` üzerinde dönülen koleksiyonun üstüne yazıyor",
        ),
    ),
    "B021": (
        (
            "f-string used as docstring. Python will interpret this as a joined string, rather "
            "than a docstring.",
            "f-string belge dizesi (docstring) olarak kullanılmış; Python bunu docstring saymaz",
        ),
    ),
    "B022": (
        (
            "No arguments passed to `contextlib.suppress`. No exceptions will be suppressed and "
            "therefore this context manager is redundant",
            "`contextlib.suppress` argümansız çağrılmış; hiçbir hatayı bastırmaz, gereksiz",
        ),
    ),
    "B023": (
        (
            "Function definition does not bind loop variable `{name}`",
            "Fonksiyon tanımı döngü değişkeni `{name}`'i bağlamıyor; son değeri görür",
        ),
    ),
    "B024": (
        (
            "`{name}` is an abstract base class, but it has no abstract methods or properties",
            "`{name}` soyut temel sınıf ama hiç soyut metodu ya da özelliği yok",
        ),
    ),
    "B025": (
        (
            "try-except* block with duplicate exception `{name}`",
            "try-except* bloğunda tekrarlanan hata türü `{name}`",
        ),
        (
            "try-except block with duplicate exception `{name}`",
            "try-except bloğunda tekrarlanan hata türü `{name}`",
        ),
    ),
    "B026": (
        (
            "Star-arg unpacking after a keyword argument is strongly discouraged",
            "Anahtar sözcüklü argümandan sonra `*` ile açma yapılmamalı",
        ),
    ),
    "B027": (
        (
            "`{name}` is an empty method in an abstract base class, but has no abstract decorator",
            "`{name}` soyut sınıfta boş bir metot ama `@abstractmethod` ile işaretlenmemiş",
        ),
    ),
    "B028": (
        (
            "No explicit `stacklevel` keyword argument found",
            "`warnings.warn` çağrısında `stacklevel` belirtilmemiş",
        ),
    ),
    "B029": (
        (
            "Using `except* ():` with an empty tuple does not catch anything; add exceptions to "
            "handle",
            "Boş demetle `except* ():` hiçbir hatayı yakalamaz; hata türlerini ekleyin",
        ),
        (
            "Using `except ():` with an empty tuple does not catch anything; add exceptions to "
            "handle",
            "Boş demetle `except ():` hiçbir hatayı yakalamaz; hata türlerini ekleyin",
        ),
    ),
    "B030": (
        (
            "`except*` handlers should only be exception classes or tuples of exception classes",
            "`except*` yalnızca hata sınıfları ya da bunların demetini almalı",
        ),
        (
            "`except` handlers should only be exception classes or tuples of exception classes",
            "`except` yalnızca hata sınıfları ya da bunların demetini almalı",
        ),
    ),
    "B031": (
        (
            "Using the generator returned from `itertools.groupby()` more than once will do "
            "nothing on the second usage",
            "`itertools.groupby()` üretecini ikinci kez kullanmak hiçbir şey döndürmez",
        ),
    ),
    "B032": (
        (
            "Possible unintentional type annotation (using `:`). Did you mean to assign "
            "(using `=`)?",
            "İstenmeden tür açıklaması yazılmış olabilir (`:`); atama (`=`) mı yapmak istediniz?",
        ),
    ),
    "B033": (
        (
            "Sets should not contain duplicate item `{value}`",
            "Kümede tekrarlanan eleman var: `{value}`",
        ),
        (
            "Sets should not contain duplicate items, but `{existing}` and `{value}` has the "
            "same value",
            "Kümede tekrarlanan eleman var: `{existing}` ve `{value}` aynı değer",
        ),
    ),
    "B034": (
        (
            "`{method}` should pass `{param_name}` and `flags` as keyword arguments to avoid "
            "confusion due to unintuitive argument positions",
            "`{method}` çağrısında `{param_name}` ve `flags` karışmaması için adıyla verilmeli",
        ),
    ),
    "B035": (
        (
            "Dictionary comprehension uses static key: `{key}`",
            "Sözlük üreteci sabit anahtar kullanıyor: `{key}`",
        ),
        ("Dictionary comprehension uses static key", "Sözlük üreteci sabit anahtar kullanıyor"),
    ),
    "B039": (
        (
            "Do not use mutable data structures for `ContextVar` defaults",
            "`ContextVar` varsayılanı değiştirilebilir bir yapı olmamalı",
        ),
    ),
    "B904": (
        (f"Within an `except*` clause, {_RAISE_FROM}", f"`except*` içinde {_RAISE_FROM_TR}"),
        (f"Within an `except` clause, {_RAISE_FROM}", f"`except` içinde {_RAISE_FROM_TR}"),
    ),
    "B905": (
        (
            "`zip()` without an explicit `strict=` parameter",
            "`zip()` `strict=` belirtilmeden çağrılmış; uzunluklar farklıysa veri sessizce kesilir",
        ),
    ),
    "B911": (
        (
            "`itertools.batched()` without an explicit `strict` parameter",
            "`itertools.batched()` `strict` belirtilmeden çağrılmış",
        ),
    ),
    "B912": (
        (
            "`map()` without an explicit `strict=` parameter",
            "`map()` `strict=` belirtilmeden çağrılmış; uzunluklar farklıysa veri sessizce kesilir",
        ),
    ),
    # --- sadeleştirme (SIM) ---
    "SIM101": (
        (
            "Multiple `isinstance` calls for `{name}`, merge into a single call",
            "`{name}` için birden çok `isinstance` çağrısı var; tek çağrıda birleştirin",
        ),
        (
            "Multiple `isinstance` calls for expression, merge into a single call",
            "Aynı ifade için birden çok `isinstance` çağrısı var; tek çağrıda birleştirin",
        ),
    ),
    "SIM102": (
        (
            "Use a single `if` statement instead of nested `if` statements",
            "İç içe `if` yerine tek bir `if` kullanın",
        ),
    ),
    "SIM103": (
        ("Return the condition `{condition}` directly", "`{condition}` koşulunu doğrudan döndürün"),
        ("Return the negated condition directly", "Koşulun tersini doğrudan döndürün"),
        ("Return the condition directly", "Koşulu doğrudan döndürün"),
    ),
    "SIM105": (
        (
            "Use `contextlib.suppress({exception})` instead of `try`-`except`-`pass`",
            "`try`-`except`-`pass` yerine `contextlib.suppress({exception})` kullanın",
        ),
    ),
    "SIM107": (
        (
            "Don't use `return` in `try`-`except` and `finally`",
            "`try`-`except` ile `finally` içinde birlikte `return` kullanmayın",
        ),
    ),
    "SIM108": (
        (
            "Use ternary operator `{contents}` instead of `if`-`else`-block",
            "`if`-`else` bloğu yerine tek satırlık koşul kullanın: `{contents}`",
        ),
        (
            "Use binary operator `{contents}` instead of `if`-`else`-block",
            "`if`-`else` bloğu yerine `{contents}` kullanın",
        ),
    ),
    "SIM109": (
        (
            "Use `{replacement}` instead of multiple equality comparisons",
            "Birden çok eşitlik karşılaştırması yerine `{replacement}` kullanın",
        ),
    ),
    "SIM110": (
        (
            "Use `{replacement}` instead of `for` loop",
            "`for` döngüsü yerine `{replacement}` kullanın",
        ),
    ),
    "SIM112": (
        (
            "Use capitalized environment variable `{expected}` instead of `{actual}`",
            "Ortam değişkeni büyük harfle yazılmalı: `{actual}` yerine `{expected}`",
        ),
        ("Use capitalized environment variable", "Ortam değişkeni adı büyük harfle yazılmalı"),
    ),
    "SIM113": (
        (
            "Use `enumerate()` for index variable `{index}` in `for` loop",
            "`for` döngüsündeki sayaç `{index}` için `enumerate()` kullanın",
        ),
    ),
    "SIM114": (
        (
            "Combine `if` branches using logical `or` operator",
            "Aynı işi yapan `if` dallarını `or` ile birleştirin",
        ),
    ),
    "SIM115": (
        (
            "Use a context manager for opening files",
            "Dosyayı `with open(...)` ile açın; aksi halde kapanmayabilir",
        ),
    ),
    "SIM116": (
        (
            "Use a dictionary instead of consecutive `if` statements",
            "Art arda `if` yerine sözlük kullanın",
        ),
    ),
    "SIM117": (
        (
            "Use a single `with` statement with multiple contexts instead of nested `with` "
            "statements",
            "İç içe `with` yerine birden çok bağlamlı tek bir `with` kullanın",
        ),
    ),
    "SIM118": (
        (
            "Use `key {operator} dict` instead of `key {operator} dict.keys()`",
            "`key {operator} dict.keys()` yerine `key {operator} dict` kullanın",
        ),
    ),
    "SIM201": (
        (
            "Use `{left} != {right}` instead of `not {left} == {right}`",
            "`not {left} == {right}` yerine `{left} != {right}` kullanın",
        ),
    ),
    "SIM202": (
        (
            "Use `{left} == {right}` instead of `not {left} != {right}`",
            "`not {left} != {right}` yerine `{left} == {right}` kullanın",
        ),
    ),
    "SIM208": (
        (
            "Use `{expr}` instead of `not (not {expr})`",
            "`not (not {expr})` yerine `{expr}` kullanın",
        ),
    ),
    "SIM210": (
        (
            "Remove unnecessary `True if ... else False`",
            "Gereksiz `True if ... else False` silinmeli",
        ),
        (
            "Use `bool(...)` instead of `True if ... else False`",
            "`True if ... else False` yerine `bool(...)` kullanın",
        ),
    ),
    "SIM211": (
        (
            "Use `not ...` instead of `False if ... else True`",
            "`False if ... else True` yerine `not ...` kullanın",
        ),
    ),
    "SIM212": (
        (
            "Use `{expr_else} if {expr_else} else {expr_body}` instead of "
            "`{expr_body} if not {expr_else} else {expr_else}`",
            "`{expr_body} if not {expr_else} else {expr_else}` yerine "
            "`{expr_else} if {expr_else} else {expr_body}` kullanın",
        ),
    ),
    "SIM220": (
        (
            "Use `False` instead of `{name} and not {name}`",
            "`{name} and not {name}` her zaman `False`; `False` kullanın",
        ),
    ),
    "SIM221": (
        (
            "Use `True` instead of `{name} or not {name}`",
            "`{name} or not {name}` her zaman `True`; `True` kullanın",
        ),
    ),
    "SIM222": (("Use `{expr}` instead of `{replaced}`", "`{replaced}` yerine `{expr}` kullanın"),),
    "SIM223": (("Use `{expr}` instead of `{replaced}`", "`{replaced}` yerine `{expr}` kullanın"),),
    "SIM300": (
        (
            "Yoda condition detected",
            "Ters koşul (Yoda): sabit değer karşılaştırmanın sağında olmalı",
        ),
    ),
    "SIM401": (
        ("Use `{contents}` instead of an `if` block", "`if` bloğu yerine `{contents}` kullanın"),
    ),
    "SIM905": (
        (
            "Consider using a list literal instead of `str.{arg0}`",
            "`str.{arg0}` yerine doğrudan liste yazmayı düşünün",
        ),
    ),
    "SIM910": (
        ("Use `{expected}` instead of `{actual}`", "`{actual}` yerine `{expected}` kullanın"),
        (
            "Use `dict.get()` without default value",
            "`dict.get()` varsayılan `None` ile yazılmasın; varsayılanı çıkarın",
        ),
    ),
    "SIM911": (
        ("Use `{expected}` instead of `{actual}`", "`{actual}` yerine `{expected}` kullanın"),
        (
            "Use `dict.items()` instead of `zip(dict.keys(), dict.values())`",
            "`zip(dict.keys(), dict.values())` yerine `dict.items()` kullanın",
        ),
    ),
    # --- performans (PERF) ---
    "PERF101": (
        (
            "Do not cast an iterable to `list` before iterating over it",
            "Üzerinde dönmeden önce `list`'e çevirmeyin; gereksiz kopya oluşur",
        ),
    ),
    "PERF102": (
        (
            "When using only the {subset} of a dict use the `{subset}()` method",
            "Sözlüğün yalnızca {subset} kısmı kullanılıyorsa `{subset}()` metodunu kullanın",
        ),
    ),
    "PERF203": (
        (
            "`try`-`except` within a loop incurs performance overhead",
            "Döngü içindeki `try`-`except` performans maliyeti getirir",
        ),
    ),
    "PERF401": (
        (
            "Use {message_str} to create a transformed list",
            "Dönüştürülmüş liste oluşturmak için {message_str} kullanın",
        ),
    ),
    "PERF402": (
        (
            "Use `list` or `list.copy` to create a copy of a list",
            "Listeyi kopyalamak için `list` ya da `list.copy` kullanın",
        ),
    ),
    "PERF403": (
        (
            "Use a dictionary comprehension instead of {modifier} for-loop",
            "{modifier} for döngüsü yerine sözlük üreteci kullanın",
        ),
        (
            "Use `dict.update` instead of {modifier} for-loop",
            "{modifier} for döngüsü yerine `dict.update` kullanın",
        ),
    ),
    # --- pycodestyle (E) ---
    "E401": (("Multiple imports on one line", "Tek satırda birden çok import var"),),
    "E402": (
        (
            "Module level import not at top of cell",
            "Modül düzeyindeki import hücrenin başında değil",
        ),
        (
            "Module level import not at top of file",
            "Modül düzeyindeki import dosyanın başında değil",
        ),
    ),
    "E701": (
        (
            "Multiple statements on one line (colon)",
            "Tek satırda birden çok deyim var (iki nokta sonrası)",
        ),
    ),
    "E702": (
        (
            "Multiple statements on one line (semicolon)",
            "Tek satırda birden çok deyim var (noktalı virgül)",
        ),
    ),
    "E703": (
        ("Statement ends with an unnecessary semicolon", "Deyim gereksiz noktalı virgülle bitiyor"),
    ),
    "E711": (
        (
            "Comparison to `None` should be `cond is None`",
            "`None` ile karşılaştırma `is None` ile yapılmalı",
        ),
        (
            "Comparison to `None` should be `cond is not None`",
            "`None` ile karşılaştırma `is not None` ile yapılmalı",
        ),
    ),
    "E712": (
        (
            "Avoid equality comparisons to `True`; use `{cond}:` for truth checks",
            "`True` ile `==` karşılaştırması yapmayın; doğrudan `{cond}:` yazın",
        ),
        (
            "Avoid inequality comparisons to `True`; use `not {cond}:` for false checks",
            "`True` ile `!=` karşılaştırması yapmayın; `not {cond}:` yazın",
        ),
        (
            "Avoid equality comparisons to `False`; use `not {cond}:` for false checks",
            "`False` ile `==` karşılaştırması yapmayın; `not {cond}:` yazın",
        ),
        (
            "Avoid inequality comparisons to `False`; use `{cond}:` for truth checks",
            "`False` ile `!=` karşılaştırması yapmayın; doğrudan `{cond}:` yazın",
        ),
    ),
    "E713": (("Test for membership should be `not in`", "Üyelik denetimi `not in` ile yazılmalı"),),
    "E714": (
        ("Test for object identity should be `is not`", "Kimlik denetimi `is not` ile yazılmalı"),
    ),
    "E721": (
        (
            "Use `is` and `is not` for type comparisons, or `isinstance()` for isinstance checks",
            "Tür karşılaştırması için `is` / `is not` ya da `isinstance()` kullanın",
        ),
    ),
    "E722": (
        (
            "Do not use bare `except`",
            "Çıplak `except` kullanmayın; tüm hataları (Ctrl+C dahil) yutar, hata türünü yazın",
        ),
    ),
    "E731": (
        (
            "Do not assign a `lambda` expression, use a `def`",
            "`lambda` bir değişkene atanmamalı; `def` kullanın",
        ),
    ),
    "E741": (("Ambiguous variable name: `{name}`", "Karışabilecek değişken adı: `{name}`"),),
    "E742": (("Ambiguous class name: `{name}`", "Karışabilecek sınıf adı: `{name}`"),),
    "E743": (("Ambiguous function name: `{name}`", "Karışabilecek fonksiyon adı: `{name}`"),),
    "E902": (("{message}", "Dosya okunamadı: {message}"),),
    # --- pyflakes (F) ---
    "F401": (
        (
            "`{name}` imported but unused; consider using `importlib.util.find_spec` to test for "
            "availability",
            "`{name}` içe aktarılmış ama kullanılmıyor; varlığını denetlemek için "
            "`importlib.util.find_spec` kullanın",
        ),
        (
            "`{name}` imported but unused; consider removing, adding to `__all__`, or using a "
            "redundant alias",
            "`{name}` içe aktarılmış ama kullanılmıyor; silin ya da `__all__`'a ekleyin",
        ),
        ("`{name}` imported but unused", "`{name}` içe aktarılmış ama kullanılmıyor"),
    ),
    "F402": (
        (
            "Import `{name}` from {row} shadowed by loop variable",
            "{row} içe aktarılan `{name}` döngü değişkeniyle gölgeleniyor",
        ),
    ),
    "F403": (
        (
            "`from {name} import *` used; unable to detect undefined names",
            "`from {name} import *` kullanılmış; tanımsız isimler tespit edilemiyor",
        ),
    ),
    "F404": (
        (
            "`from __future__` imports must occur at the beginning of the file",
            "`from __future__` importları dosyanın en başında olmalı",
        ),
    ),
    "F405": (
        (
            "`{name}` may be undefined, or defined from star imports",
            "`{name}` tanımsız olabilir ya da `import *` ile gelmiş olabilir",
        ),
    ),
    "F406": (
        (
            "`from {name} import *` only allowed at module level",
            "`from {name} import *` yalnızca modül düzeyinde kullanılabilir",
        ),
    ),
    "F407": (("Future feature `{name}` is not defined", "`{name}` adlı __future__ özelliği yok"),),
    "F501": (
        (
            "`%`-format string has invalid format string: {message}",
            "`%` biçim dizesi geçersiz: {message}",
        ),
    ),
    "F502": (
        (
            "`%`-format string expected mapping but got sequence",
            "`%` biçim dizesi sözlük bekliyor ama dizi verilmiş",
        ),
    ),
    "F503": (
        (
            "`%`-format string expected sequence but got mapping",
            "`%` biçim dizesi dizi bekliyor ama sözlük verilmiş",
        ),
    ),
    "F504": (
        (
            "`%`-format string has unused named argument(s): {message}",
            "`%` biçim dizesinde kullanılmayan adlı argüman var: {message}",
        ),
    ),
    "F505": (
        (
            "`%`-format string is missing argument(s) for placeholder(s): {message}",
            "`%` biçim dizesinde yer tutucu için argüman eksik: {message}",
        ),
    ),
    "F506": (
        (
            "`%`-format string has mixed positional and named placeholders",
            "`%` biçim dizesi sıralı ve adlı yer tutucuları karıştırıyor",
        ),
    ),
    "F507": (
        (
            "`%`-format string has {wanted} placeholder(s) but {got} substitution(s)",
            "`%` biçim dizesinde {wanted} yer tutucu var ama {got} değer verilmiş",
        ),
    ),
    "F508": (
        (
            "`%`-format string `*` specifier requires sequence",
            "`%` biçim dizesindeki `*` belirteci dizi gerektirir",
        ),
    ),
    "F509": (
        (
            "`%`-format string has unsupported format character `{char}`",
            "`%` biçim dizesinde desteklenmeyen karakter: `{char}`",
        ),
    ),
    "F521": (
        (
            "`.format` call has invalid format string: {message}",
            "`.format` çağrısında geçersiz biçim dizesi: {message}",
        ),
    ),
    "F522": (
        (
            "`.format` call has unused named argument(s): {message}",
            "`.format` çağrısında kullanılmayan adlı argüman var: {message}",
        ),
    ),
    "F523": (
        (
            "`.format` call has unused arguments at position(s): {message}",
            "`.format` çağrısında kullanılmayan argüman var (sıra: {message})",
        ),
    ),
    "F524": (
        (
            "`.format` call is missing argument(s) for placeholder(s): {message}",
            "`.format` çağrısında yer tutucu için argüman eksik: {message}",
        ),
    ),
    "F525": (
        (
            "`.format` string mixes automatic and manual numbering",
            "`.format` dizesi otomatik ve elle numaralandırmayı karıştırıyor",
        ),
    ),
    "F541": (
        ("f-string without any placeholders", "f-string içinde hiç yer tutucu yok; `f` gereksiz"),
    ),
    "F601": (
        (
            "Dictionary key literal `{name}` repeated (`{name2}` hashes to the same value as "
            "`{existing}`)",
            "Sözlük anahtarı `{name}` tekrarlanıyor (`{name2}` ile `{existing}` aynı anahtar)",
        ),
        ("Dictionary key literal `{name}` repeated", "Sözlük anahtarı `{name}` tekrarlanıyor"),
        ("Dictionary key literal repeated", "Sözlük anahtarı tekrarlanıyor"),
    ),
    "F602": (
        ("Dictionary key `{name}` repeated", "Sözlük anahtarı `{name}` tekrarlanıyor"),
        ("Dictionary key repeated", "Sözlük anahtarı tekrarlanıyor"),
    ),
    "F621": (
        (
            "Too many expressions in star-unpacking assignment",
            "Yıldızlı açma atamasında çok fazla ifade var",
        ),
    ),
    "F622": (("Two starred expressions in assignment", "Atamada iki yıldızlı ifade var"),),
    "F631": (
        (
            "Assert test is a non-empty tuple, which is always `True`",
            "`assert` boş olmayan bir demeti denetliyor; sonuç her zaman `True`",
        ),
    ),
    "F632": (
        (
            "Use `==` to compare constant literals",
            "Sabit değerleri `is` ile değil `==` ile karşılaştırın",
        ),
        (
            "Use `!=` to compare constant literals",
            "Sabit değerleri `is not` ile değil `!=` ile karşılaştırın",
        ),
    ),
    "F633": (
        ("Use of `>>` is invalid with `print` function", "`print` fonksiyonuyla `>>` kullanılamaz"),
    ),
    "F634": (
        (
            "If test is a tuple, which is always `True`",
            "`if` bir demeti denetliyor; sonuç her zaman `True`",
        ),
    ),
    "F701": (("`break` outside loop", "`break` döngü dışında"),),
    "F702": (("`continue` not properly in loop", "`continue` döngü içinde değil"),),
    "F704": (
        ("`{keyword}` statement outside of a function", "`{keyword}` deyimi fonksiyon dışında"),
    ),
    "F706": (
        (
            "`return` statement outside of a function/method",
            "`return` fonksiyon ya da metot dışında",
        ),
    ),
    "F707": (
        (
            "An `except` block as not the last exception handler",
            "Çıplak `except` son hata yakalayıcı olmalı",
        ),
    ),
    "F722": (
        (
            "Syntax error in forward annotation: {parse_error}",
            "İleri tür açıklamasında sözdizimi hatası: {parse_error}",
        ),
    ),
    "F811": (
        (
            "Redefinition of unused `{name}` from {row}",
            "Kullanılmayan `{name}` yeniden tanımlanıyor (ilk tanım: {row})",
        ),
    ),
    "F821": (
        ("Undefined name `{name}`. {tip}", "Tanımsız isim `{name}`"),
        ("Undefined name `{name}`", "Tanımsız isim `{name}`"),
    ),
    "F822": (("Undefined name `{name}` in `__all__`", "`__all__` içinde tanımsız isim `{name}`"),),
    "F823": (
        (
            "Local variable `{name}` referenced before assignment",
            "Yerel değişken `{name}` değer atanmadan önce kullanılıyor",
        ),
    ),
    "F841": (
        (
            "Local variable `{name}` is assigned to but never used",
            "Yerel değişken `{name}` atanmış ama hiç kullanılmıyor",
        ),
    ),
    "F842": (
        (
            "Local variable `{name}` is annotated but never used",
            "Yerel değişken `{name}` tanımlanmış ama hiç kullanılmıyor",
        ),
    ),
    "F901": (
        (
            "`raise NotImplemented` should be `raise NotImplementedError`",
            "`raise NotImplemented` yerine `raise NotImplementedError` yazılmalı",
        ),
    ),
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_SYNTAX_PREFIX = "SyntaxError: "


@cache
def _compiled(english: str) -> re.Pattern[str]:
    """Turn a ruff message format into a regex; a repeated placeholder must match the same text."""
    parts: list[str] = []
    seen: set[str] = set()
    last = 0
    for match in _PLACEHOLDER.finditer(english):
        parts.append(re.escape(english[last : match.start()]))
        name = match.group(1)
        parts.append(f"(?P={name})" if name in seen else f"(?P<{name}>.+?)")
        seen.add(name)
        last = match.end()
    parts.append(re.escape(english[last:]))
    return re.compile("".join(parts) + r"\Z", re.DOTALL)


def _fill(turkish: str, values: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), "…"), turkish)


# --------------------------------------------------------------------------- syntax errors
# Ruff reports parse errors with the code `invalid-syntax` (older versions: no code).
# Their texts come from the parser, so they are matched as patterns, not by rule.

SYNTAX_RULES = frozenset({"syntax-error", "invalid-syntax"})

# Words that appear inside "Expected X, found Y" style messages.
_TOKENS: dict[str, str] = {
    "newline": "satır sonu",
    "end of file": "dosya sonu",
    "dedent": "girinti azalması",
    "indent": "girinti",
    "identifier": "isim",
    "name": "isim",
    "string": "metin",
    "int": "sayı",
    "float": "sayı",
    "an expression": "bir ifade",
    "a statement": "bir deyim",
    "an identifier": "bir isim",
    "a parameter or the end of the parameter list": "bir parametre ya da parametre listesinin sonu",
    "an expression or a ')'": "bir ifade ya da `)`",
    "an expression or a ']'": "bir ifade ya da `]`",
    "an expression or a '}'": "bir ifade ya da `}`",
    "function definition": "fonksiyon tanımı",
    "class definition": "sınıf tanımı",
}

_STATEMENT = re.compile(r"`(\w+)` (statement|clause)")
_OR_LIST = re.compile(r"\s+or\s+")


def _token(text: str) -> str:
    text = text.strip()
    if text in _TOKENS:
        return _TOKENS[text]
    statement = _STATEMENT.fullmatch(text)
    if statement:
        return (
            f"`{statement.group(1)}` {'deyimi' if statement.group(2) == 'statement' else 'bloğu'}"
        )
    if " or " in text:
        return " ya da ".join(_token(part) for part in _OR_LIST.split(text))
    return text


_SYNTAX: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str]], ...] = tuple(
    (re.compile(pattern + r"\Z", re.DOTALL), build)
    for pattern, build in (
        (r"Unexpected indentation", lambda m: "Beklenmeyen girinti: bu satır fazladan içeride"),
        (
            r"unindent does not match any outer indentation level",
            lambda m: "Girinti hiçbir üst satırın girintisiyle eşleşmiyor",
        ),
        (
            r"Expected an indented block after (?P<what>.+)",
            lambda m: (
                f"{_token(m['what'])} sonrasında girintili (içeriden başlayan) blok bekleniyordu"
            ),
        ),
        (
            r"Expected an indented block",
            lambda m: "Girintili (içeriden başlayan) blok bekleniyordu",
        ),
        (
            r"Expected `except` or `finally` after `try` block",
            lambda m: "`try` bloğundan sonra `except` ya da `finally` bekleniyordu",
        ),
        (
            r"Expected `def`, `with` or `for` to follow `async`, found (?P<found>.+)",
            lambda m: (
                f"`async` sonrasında `def`, `with` ya da `for` bekleniyordu, "
                f"{_token(m['found'])} bulundu"
            ),
        ),
        (
            r"Expected one or more symbol names after import",
            lambda m: "`import` sonrasında en az bir isim bekleniyordu",
        ),
        (
            r"Expected one or more keyword parameter after `\*` separator",
            lambda m: "`*` ayıracından sonra en az bir adlı parametre bekleniyordu",
        ),
        (
            r"Expected dedent, found end of file",
            lambda m: "Girintili blok kapanmadan dosya bitti",
        ),
        (
            r"Expected (?P<want>.+?), found (?P<found>.+)",
            lambda m: f"{_token(m['want'])} bekleniyordu, {_token(m['found'])} bulundu",
        ),
        (r"Expected (?P<want>.+)", lambda m: f"{_token(m['want'])} bekleniyordu"),
        (r"Got unexpected token (?P<tok>.+)", lambda m: f"Beklenmeyen karakter: {m['tok']}"),
        (r"unexpected EOF while parsing", lambda m: "Kod tamamlanmadan dosya bitti"),
        (
            r"Simple statements must be separated by newlines or semicolons",
            lambda m: "Aynı satırdaki deyimler satır sonu ya da noktalı virgülle ayrılmalı",
        ),
        (r"missing closing quote in string literal", lambda m: "Metnin kapanış tırnağı eksik"),
        (
            r"unterminated triple-quoted string literal",
            lambda m: "Üç tırnaklı metnin kapanış tırnakları eksik",
        ),
        (r"Invalid assignment target", lambda m: "Bu ifadeye değer atanamaz"),
        (r"Invalid augmented assignment target", lambda m: "Bu ifadeye `+=` gibi atama yapılamaz"),
        (r"Invalid delete target", lambda m: "Bu ifade `del` ile silinemez"),
        (
            r"Invalid annotated assignment target",
            lambda m: "Bu ifadeye tür açıklamalı atama yapılamaz",
        ),
        (r"Invalid decimal integer literal", lambda m: "Geçersiz tam sayı yazımı"),
        (r"Invalid hexadecimal integer literal", lambda m: "Geçersiz onaltılık sayı yazımı"),
        (r"Invalid octal integer literal", lambda m: "Geçersiz sekizlik sayı yazımı"),
        (r"Invalid binary integer literal", lambda m: "Geçersiz ikilik sayı yazımı"),
        (
            r"Duplicate keyword argument (?P<name>.+)",
            lambda m: f"Aynı adlı argüman iki kez verilmiş: {m['name']}",
        ),
        (
            r"Duplicate parameter (?P<name>.+)",
            lambda m: f"Aynı adlı parametre iki kez tanımlanmış: {m['name']}",
        ),
        (
            r"Positional argument cannot follow keyword argument",
            lambda m: "Sıralı argüman, adlı argümandan sonra gelemez",
        ),
        (
            r"Positional argument cannot follow keyword argument unpacking",
            lambda m: "Sıralı argüman, `**` ile açılan argümandan sonra gelemez",
        ),
        (
            r"Parameter without a default cannot follow a parameter with a default",
            lambda m: (
                "Varsayılan değeri olmayan parametre, varsayılanı olan parametreden sonra gelemez"
            ),
        ),
        (
            r"Parameter cannot follow var-keyword parameter",
            lambda m: "`**kwargs` parametresinden sonra başka parametre gelemez",
        ),
        (
            r"Starred expression cannot be used here",
            lambda m: "Yıldızlı ifade (`*`) burada kullanılamaz",
        ),
        (
            r"Exception missing in `raise` statement with cause",
            lambda m: "`raise ... from` deyiminde fırlatılacak hata eksik",
        ),
        (
            r"nonlocal declaration not allowed at module level",
            lambda m: "`nonlocal` modül düzeyinde kullanılamaz",
        ),
        (
            r"f-string: (?P<rest>.+)",
            lambda m: f"f-string hatası: {_FSTRING.get(m['rest'], m['rest'])}",
        ),
    )
)

_FSTRING: dict[str, str] = {
    "invalid conversion character": "geçersiz dönüştürme karakteri (yalnız !r, !s, !a)",
    "expecting '}'": "`}` bekleniyordu",
    "single '}' is not allowed": "tek başına `}` kullanılamaz",
    "valid expression required before '}'": "`}` öncesinde geçerli bir ifade gerekli",
    "unterminated string": "metin kapanmamış",
}


def _capitalize(text: str) -> str:
    """Upper-case the first letter the Turkish way (i -> İ)."""
    if not text or not text[0].isalpha():
        return text
    first = "İ" if text[0] == "i" else text[0].upper()
    return first + text[1:]


def translate_syntax(message: str) -> str:
    """Turkish text for a parse error; an unknown wording keeps ruff's text after a Turkish lead."""
    detail = message.removeprefix(_SYNTAX_PREFIX)
    for pattern, build in _SYNTAX:
        match = pattern.match(detail)
        if match is not None:
            return _capitalize(build(match))
    return f"Sözdizimi hatası, Python bu satırı okuyamıyor (ruff: {detail})"


def translate(rule: str | None, message: str) -> str:
    """Turkish text for a ruff finding; unknown rules keep ruff's message."""
    if rule is None or rule in SYNTAX_RULES:
        return translate_syntax(message)
    variants = MESSAGES.get(rule)
    if not variants:
        return message
    for english, turkish in variants:
        match = _compiled(english).match(message)
        if match is not None:
            return _fill(turkish, match.groupdict())
    return _fill(variants[0][1], {})
