"""Official-source directory. Entries are destinations, not claims of live integrations."""

COUNTRIES = [
    {"code": "URU", "name": "Uruguay", "flag": "🇺🇾", "tracks": ["Maroñas", "Las Piedras", "Melo", "Paysandú", "Colonia"]},
    {"code": "USA", "name": "Estados Unidos", "flag": "🇺🇸", "tracks": ["Churchill Downs", "Belmont Park", "Saratoga", "Santa Anita", "Keeneland", "Gulfstream Park"]},
    {"code": "FRA", "name": "Francia", "flag": "🇫🇷", "tracks": ["ParisLongchamp", "Chantilly", "Deauville"]},
    {"code": "GBR", "name": "Gran Bretaña", "flag": "🇬🇧", "tracks": ["Ascot", "Epsom", "Newmarket", "York"]},
    {"code": "JPN", "name": "Japón", "flag": "🇯🇵", "tracks": ["Tokyo", "Nakayama", "Kyoto", "Hanshin"]},
    {"code": "HKG", "name": "Hong Kong", "flag": "🇭🇰", "tracks": ["Sha Tin", "Happy Valley"]},
    {"code": "BRA", "name": "Brasil", "flag": "🇧🇷", "tracks": ["Gávea", "Cidade Jardim", "Cristal"]},
    {"code": "ARG", "name": "Argentina", "flag": "🇦🇷", "tracks": ["Palermo", "San Isidro", "La Plata"]},
    {"code": "CHI", "name": "Chile", "flag": "🇨🇱", "tracks": ["Club Hípico de Santiago", "Hipódromo Chile", "Valparaíso Sporting"]},
]

SOURCES = [
    {"id": "uy-studbook", "country": "URU", "name": "Stud Book Uruguayo", "kind": "pedigree", "url": "https://www.studbook.com.uy", "hosts": ["www.studbook.com.uy", "studbook.com.uy", "backend.studbook.com.uy"]},
    {"id": "uy-maronas", "country": "URU", "name": "Maroñas · Hípica", "kind": "results", "url": "https://hipica.maronas.com.uy", "hosts": ["hipica.maronas.com.uy", "www.maronas.com.uy", "mobile-rest-services-v3.azurewebsites.net"]},
    {"id": "us-studbook", "country": "USA", "name": "The Jockey Club", "kind": "pedigree", "url": "https://www.jockeyclub.com", "hosts": ["www.jockeyclub.com"]},
    {"id": "us-equibase", "country": "USA", "name": "Equibase", "kind": "results", "url": "https://www.equibase.com", "hosts": ["www.equibase.com"]},
    {"id": "fr-galop", "country": "FRA", "name": "France Galop", "kind": "both", "url": "https://www.france-galop.com", "hosts": ["www.france-galop.com"]},
    {"id": "gb-weatherbys", "country": "GBR", "name": "Weatherbys · General Stud Book", "kind": "pedigree", "url": "https://www.weatherbys.co.uk", "hosts": ["www.weatherbys.co.uk"]},
    {"id": "gb-bha", "country": "GBR", "name": "British Horseracing Authority", "kind": "results", "url": "https://www.britishhorseracing.com", "hosts": ["www.britishhorseracing.com"]},
    {"id": "jp-jbis", "country": "JPN", "name": "JBIS · Japan Bloodhorse Breeders’ Association", "kind": "pedigree", "url": "https://www.jbis.jp", "hosts": ["www.jbis.jp"]},
    {"id": "jp-jra", "country": "JPN", "name": "Japan Racing Association", "kind": "results", "url": "https://www.jra.go.jp", "hosts": ["www.jra.go.jp", "japanracing.jp"]},
    {"id": "hk-jockeyclub", "country": "HKG", "name": "Hong Kong Jockey Club", "kind": "both", "url": "https://racing.hkjc.com", "hosts": ["racing.hkjc.com", "www.hkjc.com"]},
    {"id": "br-studbook", "country": "BRA", "name": "Stud Book Brasileiro", "kind": "pedigree", "url": "https://www.studbook.com.br", "hosts": ["www.studbook.com.br", "studbook.com.br"]},
    {"id": "br-jcb", "country": "BRA", "name": "Jockey Club Brasileiro", "kind": "results", "url": "https://www.jcb.com.br", "hosts": ["www.jcb.com.br", "jcb.com.br", "site.jcb.com.br"]},
    {"id": "ar-studbook", "country": "ARG", "name": "Stud Book Argentino", "kind": "both", "url": "https://www.studbook.org.ar", "hosts": ["www.studbook.org.ar"]},
    {"id": "cl-studbook", "country": "CHI", "name": "Stud Book de Chile", "kind": "both", "url": "https://www.studbook.cl", "hosts": ["www.studbook.cl"]},
]
