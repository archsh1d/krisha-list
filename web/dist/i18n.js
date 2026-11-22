"use strict";

// Source strings are kept in Russian so existing listing data is never rewritten.
// Only known interface strings are translated; property titles and addresses stay as collected.
(() => {
  const STORAGE_KEY = "krisha-list.language.v1";
  const locales = { ru: "ru-RU", kk: "kk-KZ", en: "en-US" };
  const cityLabels = {
    almaty: ["Алматы", "Almaty", "Алматы"], astana: ["Астана", "Astana", "Астана"],
    shymkent: ["Шымкент", "Shymkent", "Шымкент"], aktau: ["Актау", "Aktau", "Ақтау"],
    aktobe: ["Актобе", "Aktobe", "Ақтөбе"], atyrau: ["Атырау", "Atyrau", "Атырау"],
    karaganda: ["Караганда", "Karaganda", "Қарағанды"], pavlodar: ["Павлодар", "Pavlodar", "Павлодар"],
    semej: ["Семей", "Semey", "Семей"], taraz: ["Тараз", "Taraz", "Тараз"]
  };
  const messages = {
    "Сбор и анализ объявлений недвижимости по области и фильтрам": ["Collect and analyze property listings by area and filters", "Аумақ пен сүзгілер бойынша жылжымайтын мүлік хабарландыруларын жинау және талдау"],
    "Krisha List — каталог недвижимости": ["Krisha List — property catalog", "Krisha List — жылжымайтын мүлік каталогы"],
    "Krisha List — главная": ["Krisha List — home", "Krisha List — басты бет"],
    "Инструмент исследования": ["Research tool", "Зерттеу құралы"],
    "Язык интерфейса": ["Interface language", "Интерфейс тілі"],
    "ГОРОДА / НЕДВИЖИМОСТЬ": ["CITIES / PROPERTY", "ҚАЛАЛАР / ЖЫЛЖЫМАЙТЫН МҮЛІК"],
    "Объявления. В деталях.": ["Listings. In detail.", "Хабарландырулар. Толық мәлімет."],
    "Выберите область, соберите данные и сравнивайте объекты в таблице и на карте.": ["Choose an area, collect data, and compare properties in the table and on the map.", "Аумақты таңдап, деректерді жинаңыз да, нысандарды кесте мен картада салыстырыңыз."],
    "Сбор объявлений": ["Collect listings", "Хабарландыруларды жинау"],
    "Источник: Krisha.kz": ["Source: Krisha.kz", "Дереккөз: Krisha.kz"],
    "Недвижимость": ["Property", "Жылжымайтын мүлік"],
    "Дома и дачи": ["Houses and cottages", "Үйлер мен саяжайлар"],
    "Квартиры": ["Apartments", "Пәтерлер"],
    "Объём сбора": ["Collection size", "Жинау көлемі"],
    "1 страница": ["1 page", "1 бет"],
    "До 10 страниц": ["Up to 10 pages", "10 бетке дейін"],
    "Все страницы": ["All pages", "Барлық беттер"],
    "Город": ["City", "Қала"],
    "Способ выбора области": ["Area selection method", "Аумақты таңдау тәсілі"],
    "По названию": ["By name", "Атауы бойынша"],
    "На карте": ["On map", "Картада"],
    "Район или микрорайон": ["District or neighborhood", "Аудан немесе шағынаудан"],
    "Начните вводить название": ["Start typing a name", "Атауын енгізе бастаңыз"],
    "Районы и микрорайоны": ["Districts and neighborhoods", "Аудандар мен шағынаудандар"],
    "Выберите район или микрорайон из подсказок.": ["Choose a district or neighborhood from the suggestions.", "Ұсыныстардан аудан немесе шағынауданды таңдаңыз."],
    "Область": ["Area", "Аумақ"],
    "Весь город": ["Entire city", "Бүкіл қала"],
    "Использовать выбранную область": ["Use selected area", "Таңдалған аумақты пайдалану"],
    "Форма области": ["Area shape", "Аумақ пішіні"],
    "Прямоугольник": ["Rectangle", "Тікбұрыш"],
    "Полигон на карте": ["Polygon on map", "Картадағы полигон"],
    "Север": ["North", "Солтүстік"], "Запад": ["West", "Батыс"],
    "Юг": ["South", "Оңтүстік"], "Восток": ["East", "Шығыс"],
    "Откройте карту кнопкой ниже, чтобы нарисовать область.": ["Open the map below to draw an area.", "Аумақты сызу үшін төмендегі батырмамен картаны ашыңыз."],
    "Точки без координат не войдут в выборку.": ["Listings without coordinates are excluded.", "Координатасы жоқ нысандар іріктемеге кірмейді."],
    "Нарисовать область на карте": ["Draw an area on the map", "Картада аумақты сызу"],
    "Фильтры Krisha": ["Krisha filters", "Krisha сүзгілері"],
    "По умолчанию": ["Default", "Әдепкі"],
    "Ссылка на выдачу": ["Search results URL", "Іздеу нәтижелерінің сілтемесі"],
    "Параметры из ссылки сохраняются; выбранный город и область заменят её расположение.": ["URL filters are preserved; the selected city and area replace its location.", "Сілтемедегі сүзгілер сақталады; таңдалған қала мен аумақ оның орналасуын алмастырады."],
    "Собрать объявления": ["Collect listings", "Хабарландыруларды жинау"],
    "Для автоматического сбора нужно ваше письменное": ["Automated collection requires your written", "Автоматты жинауға сіздің жазбаша"],
    "разрешение Kolesa": ["permission from Kolesa", "Kolesa рұқсатыңыз"],
    ". При отказе источника сервис покажет сохранённый снимок, если он есть.": [". If the source refuses access, the service shows a saved snapshot when available.", ". Дереккөз қолжетімділіктен бас тартса, сақталған көшірме бар болған жағдайда көрсетіледі."],
    "Сбор запускается локально": ["Collection runs locally", "Жинау жергілікті іске қосылады"],
    "Кнопка откроет локальный сборщик. Запустите его командой:": ["The button opens the local collector. Start it with:", "Батырма жергілікті жинағышты ашады. Оны мына пәрменмен іске қосыңыз:"],
    "Загрузить сохранённый HTML": ["Import saved HTML", "Сақталған HTML файлын жүктеу"],
    "Выбрать HTML-файлы": ["Choose HTML files", "HTML файлдарын таңдау"],
    "Посмотреть пример": ["View example", "Мысалды көру"],
    "Как сохранить страницу": ["How to save a page", "Бетті қалай сақтау керек"],
    "Откройте выдачу Krisha.kz и сохраните её как «Веб-страница, только HTML».": ["Open Krisha.kz search results and save the page as “Web page, HTML only.”", "Krisha.kz іздеу нәтижелерін ашып, бетті «Веб-бет, тек HTML» ретінде сақтаңыз."],
    "ВАША ВЫБОРКА": ["YOUR SELECTION", "СІЗДІҢ ІРІКТЕМЕҢІЗ"],
    "Объявления": ["Listings", "Хабарландырулар"],
    "Данные сохранены в этом браузере.": ["Data is stored in this browser.", "Деректер осы браузерде сақталған."],
    "Скачать CSV": ["Download CSV", "CSV жүктеу"],
    "Очистить": ["Clear", "Тазалау"],
    "Поиск по объявлениям": ["Search listings", "Хабарландырулардан іздеу"],
    "Адрес, описание или ID": ["Address, description, or ID", "Мекенжай, сипаттама немесе ID"],
    "Фильтры": ["Filters", "Сүзгілер"],
    "Категория": ["Category", "Санат"],
    "Все категории": ["All categories", "Барлық санаттар"],
    "Тип объекта": ["Property type", "Нысан түрі"],
    "Все типы": ["All types", "Барлық түрлер"],
    "Сортировка": ["Sort by", "Сұрыптау"],
    "Недавно добавлены": ["Recently added", "Жақында қосылғандар"],
    "Цена: по возрастанию": ["Price: low to high", "Баға: өсу ретімен"],
    "Цена: по убыванию": ["Price: high to low", "Баға: кему ретімен"],
    "Площадь: сначала больше": ["Area: largest first", "Аудан: үлкенінен бастап"],
    "Вид собранных объявлений": ["Listings view", "Жиналған хабарландырулар көрінісі"],
    "Таблица": ["Table", "Кесте"], "Карта": ["Map", "Карта"],
    "Последнее действие": ["Latest activity", "Соңғы әрекет"],
    "История сборов пока пуста.": ["No collection history yet.", "Жинау тарихы әзірге бос."],
    "История сборов": ["Collection history", "Жинау тарихы"],
    "Сводка выборки": ["Selection summary", "Іріктеме жиынтығы"],
    "Из 0 сохранённых": ["From 0 saved", "Сақталған 0 нысаннан"],
    "Дата данных появится после сбора.": ["Data date appears after collection.", "Дерек күні жинаудан кейін көрсетіледі."],
    "Сводка собранных карточек": ["Collected listing summary", "Жиналған хабарландырулар жиынтығы"],
    "в выборке": ["in selection", "іріктемеде"],
    "с координатами": ["with coordinates", "координатасы бар"],
    "медиана цены": ["median price", "бағаның медианасы"],
    "цена объекта / сот.": ["property price / sot", "нысан бағасы / сотық"],
    "изменений цены": ["price changes", "баға өзгерісі"],
    "Цена объекта в расчёте на сотку": ["Property price per sot", "Нысанның бір сотыққа шаққандағы бағасы"],
    "Цена дома с участком ÷ площадь участка. Группы менее 5 объектов без медианы.": ["House and plot price ÷ plot area. Groups under 5 have no median.", "Үй мен жер бағасы ÷ жер аумағы. 5 нысаннан аз топтарда медиана жоқ."],
    "Группировка стоимости": ["Group prices by", "Бағаны топтау"],
    "Комнаты": ["Rooms", "Бөлмелер"], "Площадь": ["Area", "Аудан"],
    "Собранные объекты на карте": ["Collected properties on map", "Жиналған нысандар картада"],
    "Карта собранных объектов": ["Map of collected properties", "Жиналған нысандар картасы"],
    "У объектов в текущей выборке нет координат.": ["Properties in this selection have no coordinates.", "Ағымдағы іріктемедегі нысандардың координаталары жоқ."],
    "Закрыть сведения об объекте": ["Close property details", "Нысан мәліметтерін жабу"],
    "ОБЛАСТЬ СБОРА": ["COLLECTION AREA", "ЖИНАУ АУМАҒЫ"],
    "Выберите область на карте": ["Choose an area on the map", "Картадан аумақты таңдаңыз"],
    "Изменения применятся после сохранения. Для нового контура отметьте минимум три точки.": ["Changes apply after saving. Mark at least three points for a new outline.", "Өзгерістер сақталғаннан кейін қолданылады. Жаңа контур үшін кемінде үш нүкте белгілеңіз."],
    "Закрыть карту без сохранения": ["Close map without saving", "Сақтамай картаны жабу"],
    "Карта для выбора области": ["Area selection map", "Аумақты таңдау картасы"],
    "Нарисовать заново": ["Draw again", "Қайта сызу"],
    "Убрать точку": ["Remove point", "Нүктені алып тастау"],
    "Отмена": ["Cancel", "Бас тарту"],
    "Сохранить область": ["Save area", "Аумақты сақтау"],
    "Krisha List · независимый инструмент": ["Krisha List · independent tool", "Krisha List · тәуелсіз құрал"],
    "API разработчикам": ["Developer API", "Әзірлеушілерге арналған API"],
    "Документация": ["Documentation", "Құжаттама"],
    "API разработчикам — Krisha List": ["Developer API — Krisha List", "Әзірлеушілерге арналған API — Krisha List"],
    "Условия источника": ["Source terms", "Дереккөз шарттары"],
    "Выберите значение": ["Choose a value", "Мәнді таңдаңыз"],
    "Ссылка задана": ["URL set", "Сілтеме берілген"],
    "Поиск по всему городу.": ["Searching the entire city.", "Бүкіл қала бойынша іздеу."],
    "Krisha отфильтрует выдачу по выбранной области.": ["Krisha filters results to the selected area.", "Krisha нәтижелерді таңдалған аумақ бойынша сүзеді."],
    "Сервис проверит адреса на загруженных страницах города. Для полного охвата выберите «Все страницы».": ["The service checks addresses on loaded city pages. Choose “All pages” for full coverage.", "Сервис жүктелген қала беттеріндегі мекенжайларды тексереді. Толық қамту үшін «Барлық беттер» таңдаңыз."],
    "Не удалось загрузить карту.": ["Could not load the map.", "Картаны жүктеу мүмкін болмады."],
    "Достигнут предел: 100 вершин.": ["Limit reached: 100 points.", "Шектеуге жетті: 100 нүкте."],
    "Удалить область": ["Remove area", "Аумақты жою"],
    "Область будет удалена после сохранения.": ["The area will be removed when you save.", "Сақтағаннан кейін аумақ жойылады."],
    "Нажмите «Нарисовать заново», чтобы отметить область.": ["Select “Draw again” to mark an area.", "Аумақты белгілеу үшін «Қайта сызу» батырмасын басыңыз."],
    "Область не ограничена.": ["Area is not restricted.", "Аумақ шектелмеген."],
    "Проверьте координаты": ["Check coordinates", "Координаталарды тексеріңіз"],
    "Пока нет объявлений": ["No listings yet", "Әзірге хабарландыру жоқ"],
    "Ничего не найдено": ["Nothing found", "Ештеңе табылмады"],
    "Соберите объявления или загрузите сохранённый HTML.": ["Collect listings or import saved HTML.", "Хабарландыруларды жинаңыз немесе сақталған HTML файлын жүктеңіз."],
    "Измените область или фильтры каталога.": ["Change the area or catalog filters.", "Аумақты немесе каталог сүзгілерін өзгертіңіз."],
    "Измените запрос или фильтры.": ["Change your search or filters.", "Іздеуді немесе сүзгілерді өзгертіңіз."],
    "Цена не указана": ["Price unavailable", "Баға көрсетілмеген"],
    "млн ₸": ["m ₸", "млн ₸"], "тыс. ₸": ["k ₸", "мың ₸"],
    "сот.": ["sot", "сотық"], "этаж": ["floor", "қабат"],
    "Координаты": ["Coordinates", "Координаталар"],
    "Изменений цены": ["Price changes", "Баға өзгерісі"],
    "Продавец": ["Seller", "Сатушы"],
    "Адрес не указан": ["Address unavailable", "Мекенжай көрсетілмеген"],
    "Квартира": ["Apartment", "Пәтер"], "Дом / дача": ["House / cottage", "Үй / саяжай"],
    "Демо": ["Demo", "Демо"], "Есть": ["Yes", "Бар"],
    "Открыть объявление": ["Open listing", "Хабарландыруды ашу"],
    "Открыть на карте ↗": ["Open on map ↗", "Картадан ашу ↗"],
    "Собранные объявления": ["Collected listings", "Жиналған хабарландырулар"],
    "Объект": ["Property", "Нысан"], "Цена": ["Price", "Баға"],
    "Параметры": ["Details", "Параметрлер"], "Расположение": ["Location", "Орналасуы"],
    "Детали": ["Details", "Толығырақ"],
    "Дополнительных сведений нет.": ["No further details.", "Қосымша мәлімет жоқ."],
    "Каталог очищен.": ["Catalog cleared.", "Каталог тазаланды."],
    "Каталог и история цен сохранены в локальной базе SQLite.": ["Catalog and price history are stored in local SQLite.", "Каталог пен баға тарихы жергілікті SQLite базасында сақталған."],
    "Собираю…": ["Collecting…", "Жиналуда…"],
    "Получаю страницы Krisha.kz. Это может занять до минуты.": ["Loading Krisha.kz pages. This may take up to a minute.", "Krisha.kz беттері жүктелуде. Бұл бір минутқа дейін созылуы мүмкін."],
    "Удалить все объявления, сохранённые в этом браузере?": ["Delete all listings saved in this browser?", "Осы браузерде сақталған барлық хабарландыруды жою керек пе?"],
    "дата неизвестна": ["date unknown", "күні белгісіз"],
    "Выполняется": ["Running", "Орындалуда"], "Пагинация завершена": ["Pagination complete", "Беттерді қарау аяқталды"],
    "Ограничен страницами": ["Page limit reached", "Бет саны шектелген"],
    "Прерван": ["Interrupted", "Үзілді"], "Доступ закрыт": ["Access denied", "Қолжетімсіз"],
    "Сохранённый снимок": ["Saved snapshot", "Сақталған көшірме"],
    "Ошибка": ["Error", "Қате"], "Импорт": ["Import", "Импорт"],
    "История сборов пока пуста": ["No collection history yet", "Жинау тарихы әзірге бос"],
    "Объекты в каталоге могут быть получены из прежних импортов.": ["Catalog properties may come from earlier imports.", "Каталогтағы нысандар бұрынғы импорттан алынуы мүмкін."],
    "Новая выдача не получена": ["No new results received", "Жаңа нәтижелер алынбады"],
    "Последнее действие — импорт": ["Latest activity — import", "Соңғы әрекет — импорт"],
    "Получена новая выдача": ["New results received", "Жаңа нәтижелер алынды"],
    "Сбор выполняется": ["Collection in progress", "Жинау орындалуда"],
    "Сбор не завершён": ["Collection incomplete", "Жинау аяқталмады"],
    "полигон": ["polygon", "полигон"], "прямоугольник": ["rectangle", "тікбұрыш"],
    "без области": ["no area", "аумақсыз"], "HTML-файл": ["HTML file", "HTML файлы"],
    "все страницы": ["all pages", "барлық беттер"],
    "страницы проверки доступа": ["access check page", "қолжетімділікті тексеру беті"],
    "позже": ["later", "кейінірек"], "предыдущего сбора": ["previous collection", "алдыңғы жинау"],
    "Недавний сбор с теми же параметрами уже сохранён.": ["A recent collection with these parameters is already saved.", "Осы параметрлермен жақында жасалған жинау сақталған."],
    "Krisha.kz вернул страницу проверки доступа.": ["Krisha.kz returned an access check page.", "Krisha.kz қолжетімділікті тексеру бетін қайтарды."],
    "Ранее сохранённые карточки остаются в каталоге.": ["Previously saved listings remain in the catalog.", "Бұрын сақталған хабарландырулар каталогта қалады."],
    "Доступные страницы выдачи пройдены до конца.": ["All available result pages were visited.", "Қолжетімді нәтижелер беттері толық қаралды."],
    "В выдаче есть следующая страница; выберите «Все страницы» для полного обхода.": ["There is another result page; choose “All pages” for complete pagination.", "Нәтижелердің келесі беті бар; толық қарау үшін «Барлық беттер» таңдаңыз."],
    "Выборка по области неполная из-за ошибки карты.": ["The area selection is incomplete due to a map error.", "Карта қатесіне байланысты аумақ іріктемесі толық емес."],
    "HTML и ответы карты сохранены локально.": ["HTML and map responses were saved locally.", "HTML мен карта жауаптары жергілікті сақталды."],
    "Не удалось собрать объявления.": ["Could not collect listings.", "Хабарландыруларды жинау мүмкін болмады."],
    "Не удалось получить страницы.": ["Could not load pages.", "Беттерді жүктеу мүмкін болмады."],
    "Пагинация зациклилась": ["Pagination loop detected", "Беттерді қарау циклі анықталды"],
    "Источник перенаправил запрос выдачи; переход не выполнен": ["The source redirected the results request; redirect was not followed", "Дереккөз нәтижелер сұрауын басқа мекенжайға бағыттады; бағыттау орындалмады"],
    "Ответ перенаправлен на другой сайт": ["Response redirected to another site", "Жауап басқа сайтқа бағытталды"],
    "Ответ перенаправлен на другую страницу": ["Response redirected to another page", "Жауап басқа бетке бағытталды"],
    "Сайт вернул не HTML": ["The site returned non-HTML content", "Сайт HTML емес мазмұн қайтарды"],
    "Пагинация вышла за пределы исходного списка": ["Pagination left the original result list", "Беттерді қарау бастапқы тізім шегінен шықты"],
    "Ответ карты не содержит словарь объявлений": ["Map response has no listing dictionary", "Карта жауабында хабарландырулар тізімі жоқ"],
    "Карта перенаправила запрос; переход не выполнен": ["Map request was redirected; redirect was not followed", "Карта сұрауы басқа мекенжайға бағытталды; бағыттау орындалмады"],
    "Ответ карты перенаправлен на другой сайт": ["Map response redirected to another site", "Карта жауабы басқа сайтқа бағытталды"],
    "Карта вернула не JSON": ["Map returned non-JSON content", "Карта JSON емес мазмұн қайтарды"],
    "Не удалось разобрать ответ карты": ["Could not parse the map response", "Карта жауабын талдау мүмкін болмады"],
    "Некорректный формат ответа карты": ["Invalid map response format", "Карта жауабының пішімі қате"],
    "Не найден основной список объявлений; возможно, сайт вернул страницу защиты": ["Main listing results were not found; the site may have returned a protection page", "Негізгі хабарландырулар тізімі табылмады; сайт қорғаныс бетін қайтарған болуы мүмкін"],
    "Живой сбор не включён при запуске сервера": ["Live collection was not enabled when starting the server", "Сервер іске қосылғанда тікелей жинау қосылмаған"],
    "Сбор уже выполняется": ["Collection is already running", "Жинау қазір орындалуда"],
    "После отказа Krisha.kz новый запрос временно отложен.": ["After Krisha.kz refused access, a new request was temporarily deferred.", "Krisha.kz қолжетімділіктен бас тартқаннан кейін жаңа сұрау уақытша кейінге қалдырылды."],
    "Координаты карты получены не полностью; выборка по области неполная": ["Map coordinates were incomplete; the area selection is incomplete", "Карта координаталары толық алынбады; аумақ іріктемесі толық емес"],
    "Укажите ссылку и число страниц от 1 до 10 либо 0 для всех": ["Enter a URL and a page count from 1 to 10, or 0 for all", "Сілтемені және 1–10 аралығындағы бет санын не барлығы үшін 0 мәнін енгізіңіз"],
    "Границы области должны быть строкой координат": ["Area bounds must be a coordinate string", "Аумақ шекарасы координаталар жолы болуы керек"],
    "Укажите либо прямоугольник, либо полигон": ["Choose a rectangle or a polygon", "Тікбұрышты немесе полигонды таңдаңыз"],
    "Укажите район или микрорайон длиной до 120 символов": ["Enter a district or neighborhood up to 120 characters", "Аудан немесе шағынаудан атауын 120 таңбаға дейін енгізіңіз"],
    "Выберите область по названию либо на карте": ["Choose an area by name or on the map", "Аумақты атауы бойынша немесе картадан таңдаңыз"],
    "Сбор остановлен. Попробуйте позже; если ошибка повторяется, уточните у Kolesa технические условия доступа.": ["Collection stopped. Try later; if this repeats, ask Kolesa about access conditions.", "Жинау тоқтады. Кейінірек көріңіз; қате қайталанса, Kolesa компаниясынан қолжетімділік шарттарын нақтылаңыз."],
    "Новая выдача не получена. Для стабильного автоматического сбора нужна настройка доступа со стороны Kolesa.": ["No new results were received. Stable automated collection requires access setup with Kolesa.", "Жаңа нәтижелер алынбады. Тұрақты автоматты жинау үшін Kolesa тарапынан қолжетімділікті баптау қажет."],
    "Сбор прерван.": ["Collection interrupted.", "Жинау үзілді."],
    "База не ответила на запрос каталога.": ["Database did not respond to the catalog request.", "Дерекқор каталог сұрауына жауап бермеді."],
    "Не удалось перенести сохранённые в браузере карточки.": ["Could not migrate listings saved in the browser.", "Браузерде сақталған хабарландыруларды көшіру мүмкін болмады."],
    "Ссылка на выдачу некорректна.": ["Invalid search results URL.", "Іздеу нәтижелерінің сілтемесі қате."],
    "Нужна HTTPS-ссылка на выдачу домов или квартир Krisha.kz.": ["Enter a Krisha.kz HTTPS URL for house or apartment results.", "Krisha.kz үй немесе пәтер нәтижелеріне HTTPS сілтемесін енгізіңіз."],
    "Параметры сбора не распознаны.": ["Collection parameters were not recognized.", "Жинау параметрлері танылмады."],
    "Некорректные границы области.": ["Invalid area bounds.", "Аумақ шекаралары қате."],
    "Тип области не распознан.": ["Area type was not recognized.", "Аумақ түрі танылмады."],
    "Параметры перенесены. Нажмите «Собрать объявления» для запуска.": ["Parameters transferred. Select “Collect listings” to start.", "Параметрлер көшірілді. Бастау үшін «Хабарландыруларды жинау» батырмасын басыңыз."],
    "Не удалось перенести параметры сбора.": ["Could not transfer collection parameters.", "Жинау параметрлерін көшіру мүмкін болмады."],
    "Полигону нужны от 3 до 100 вершин.": ["A polygon needs 3 to 100 points.", "Полигонға 3-тен 100-ге дейін нүкте қажет."],
    "Некорректные координаты полигона.": ["Invalid polygon coordinates.", "Полигон координаталары қате."],
    "Вершины полигона не должны повторяться.": ["Polygon points must be unique.", "Полигон нүктелері қайталанбауы керек."],
    "Полигон должен охватывать площадь.": ["Polygon must enclose an area.", "Полигон аумақты қамтуы керек."],
    "Стороны полигона не должны пересекаться.": ["Polygon edges must not intersect.", "Полигон қабырғалары қиылыспауы керек."],
    "Завершите полигон на карте.": ["Finish the polygon on the map.", "Картадағы полигонды аяқтаңыз."],
    "Заполните четыре границы области.": ["Enter all four area bounds.", "Аумақтың төрт шекарасын енгізіңіз."],
    "Координаты области должны быть числами.": ["Area coordinates must be numbers.", "Аумақ координаталары сан болуы керек."],
    "Северная широта должна быть больше южной.": ["North latitude must exceed south latitude.", "Солтүстік ендік оңтүстік ендіктен үлкен болуы керек."],
    "Восточная долгота должна быть больше западной.": ["East longitude must exceed west longitude.", "Шығыс бойлық батыс бойлықтан үлкен болуы керек."],
    "Основной список объявлений не найден. Проверьте, что это сохранённая страница выдачи.": ["Listing results were not found. Check that this is a saved results page.", "Хабарландырулар тізімі табылмады. Бұл сақталған нәтижелер беті екенін тексеріңіз."],
    "В файле есть список, но нет карточек. Возможно, изменилась разметка страницы.": ["The file contains a list but no cards. The page markup may have changed.", "Файлда тізім бар, бірақ карточкалар жоқ. Бет құрылымы өзгерген болуы мүмкін."],
    "Одна из карточек не содержит корректный ID, заголовок или ссылку.": ["A card has an invalid ID, title, or URL.", "Карточкалардың бірінде ID, тақырып немесе сілтеме қате."],
    "Не удалось выгрузить данные из SQLite.": ["Could not export data from SQLite.", "SQLite деректерін экспорттау мүмкін болмады."],
    "не удалось импортировать": ["import failed", "импорттау мүмкін болмады"],
    "Не удалось прочитать файл.": ["Could not read the file.", "Файлды оқу мүмкін болмады."],
    "Демонстрационный файл недоступен.": ["Demo file unavailable.", "Демо файл қолжетімсіз."],
    "Не удалось открыть пример.": ["Could not open the example.", "Мысалды ашу мүмкін болмады."],
    "Не удалось открыть локальную базу": ["Could not open local database", "Жергілікті дерекқорды ашу мүмкін болмады"],
    "Группы менее 5 объектов без медианы.": ["Groups under 5 have no median.", "5 нысаннан аз топтарда медиана жоқ."],
    "выберите категорию": ["choose a category", "санатты таңдаңыз"],
    "Сравнение стоимости": ["Price comparison", "Бағаны салыстыру"],
    "Цена квартиры за м²": ["Apartment price per m²", "Пәтердің м² бағасы"],
    "Выберите дома или квартиры: цены разных типов не объединяются.": ["Choose houses or apartments; prices for different types are not combined.", "Үйлерді немесе пәтерлерді таңдаңыз; әртүрлі нысандар бағасы біріктірілмейді."],
    "Выберите категорию в фильтрах.": ["Choose a category in the filters.", "Сүзгілерден санатты таңдаңыз."],
    "Для этой группировки не хватает данных.": ["Not enough data for this grouping.", "Бұл топтауға дерек жеткіліксіз."],
    "Нужны цена и площадь квартир.": ["Apartment price and area are required.", "Пәтер бағасы мен ауданы қажет."],
    "Нужны цена и площадь участков.": ["Plot price and area are required.", "Жер бағасы мен аумағы қажет."],
    "Менее 5 объектов": ["Fewer than 5 properties", "5 нысаннан аз"],
    "за 1 м²": ["per m²", "1 м² үшін"],
    "за 1 сот.": ["per sot", "1 сотық үшін"],
    "Даты наблюдения в текущей выборке неизвестны.": ["Observation dates are unknown for this selection.", "Бұл іріктеменің бақылау күндері белгісіз."],
    "Не удалось загрузить карту.": ["Could not load the map.", "Картаны жүктеу мүмкін болмады."],
    "Документация API · v1": ["API documentation · v1", "API құжаттамасы · v1"],
    "Для серверных интеграций": ["For server integrations", "Серверлік интеграцияларға"],
    "Ваши данные.": ["Your data.", "Сіздің деректеріңіз."],
    "Ваши сервисы.": ["Your services.", "Сіздің сервистеріңіз."],
    "Используйте сохранённые карточки, историю цен и результаты сбора через JSON API. Опубликованная страница содержит документацию; данные остаются на вашем экземпляре локального сервера.": ["Use saved listings, price history, and collection results through the JSON API. This published page contains documentation; data stays on your local server instance.", "Сақталған хабарландыруларды, баға тарихын және жинау нәтижелерін JSON API арқылы пайдаланыңыз. Жарияланған бетте тек құжаттама бар; деректер жергілікті серверіңізде қалады."],
    "Автоматический доступ к Krisha.kz и извлечение объявлений требуют собственного письменного разрешения Kolesa согласно": ["Automated access to Krisha.kz and listing extraction require your own written permission from Kolesa under", "Krisha.kz сайтына автоматты кіру және хабарландыруларды алу үшін Kolesa компаниясының жеке жазбаша рұқсаты қажет, бұл"],
    "п. 5.3 соглашения": ["section 5.3 of the agreement", "келісімнің 5.3-тармағында"],
    ". Код и API не предоставляют такого разрешения. Живой сбор может останавливаться при HTTP 468; сохранённый снимок не является свежими данными.": [". The code and API do not grant permission. Live collection may stop at HTTP 468; a saved snapshot is not fresh data.", " көрсетілген. Код пен API мұндай рұқсат бермейді. Тікелей жинау HTTP 468 кезінде тоқтауы мүмкін; сақталған көшірме жаңа дерек болып саналмайды."],
    "Запуск": ["Getting started", "Іске қосу"],
    "Создайте случайный токен длиной не менее 32 символов, сохраните его локально и запустите сервер:": ["Generate a random token of at least 32 characters, save it locally, and start the server:", "Кемінде 32 таңбалы кездейсоқ токен жасап, оны жергілікті сақтаңыз да, серверді іске қосыңыз:"],
    "По умолчанию API слушает": ["By default, the API listens on", "Әдепкіде API мына мекенжайда тыңдайды:"],
    "Для сетевой интеграции укажите": ["For network integration, use", "Желілік интеграция үшін мынаны көрсетіңіз:"],
    "и разместите его за HTTPS-прокси. Без токена сетевой запуск запрещён.": ["and place it behind an HTTPS proxy. Network startup requires a token.", "және оны HTTPS прокси артына орналастырыңыз. Токенсіз желілік іске қосуға болмайды."],
    "Маршруты": ["Endpoints", "Маршруттар"],
    "Состояние сервера": ["Server status", "Сервер күйі"],
    "Карточки, фильтры и пагинация": ["Listings, filters, and pagination", "Хабарландырулар, сүзгілер және беттеу"],
    "Карточка и история цены": ["Listing and price history", "Хабарландыру және баға тарихы"],
    "Последние запуски": ["Recent runs", "Соңғы іске қосулар"],
    "Один запуск": ["Single run", "Бір іске қосу"],
    "Сбор с ответом после завершения": ["Collection with response on completion", "Аяқталған соң жауап беретін жинау"],
    "Спецификация без токена": ["Specification without token", "Токенсіз спецификация"],
    "Для списка доступны": ["The list supports", "Тізім үшін қолжетімді:"],
    "Все параметры описаны в": ["All parameters are described in", "Барлық параметрлер мына жерде сипатталған:"],
    "Пример запроса": ["Example request", "Сұрау мысалы"],
    "Ответ содержит": ["The response contains", "Жауапта мыналар бар:"],
    "и": ["and", "және"],
    "Запрашивайте следующие страницы, пока": ["Request more pages until", "Келесі беттерді мына мәнге дейін сұраңыз:"],
    "не станет": ["becomes", "болғанша"],
    "Отдельная карточка содержит историю цен.": ["A single listing includes price history.", "Жеке хабарландыруда баға тарихы бар."],
    "Держите токен на сервере интеграции. Браузерные запросы с заголовком Origin отклоняются. API не отменяет паузы и отказы Krisha.kz при сборе.": ["Keep the token on your integration server. Browser requests with an Origin header are rejected. The API does not bypass collection delays or Krisha.kz refusals.", "Токенді интеграция серверінде сақтаңыз. Origin тақырыбы бар браузер сұраулары қабылданбайды. API жинау кезіндегі кідірістер мен Krisha.kz шектеулерін айналып өтпейді."]
  };

  // Dynamic strings are expressed as templates. Unknown data is left unchanged.
  const templates = [
    ["{n} комн.", "{n} rooms", "{n} бөлме"],
    ["6+ комн.", "6+ rooms", "6+ бөлме"],
    ["{n} этаж", "floor {n}", "{n} қабат"],
    ["{n} сот.", "{n} sot", "{n} сотық"],
    ["{n} млн ₸", "{n}m ₸", "{n} млн ₸"],
    ["{n} тыс. ₸", "{n}k ₸", "{n} мың ₸"],
    ["медиана цены · n={n}", "median price · n={n}", "бағаның медианасы · n={n}"],
    ["за 1 м² · n={n}", "per m² · n={n}", "1 м² үшін · n={n}"],
    ["цена объекта / сот. · n={n}", "property price / sot · n={n}", "нысан бағасы / сотық · n={n}"],
    ["{n} из {total} в текущей выборке", "{n} of {total} in selection", "Іріктемеде {total} нысанның {n}-і"],
    ["Последнее наблюдение: {date} · за 24 ч: {n} из {total}", "Last observed: {date} · past 24 h: {n} of {total}", "Соңғы бақылау: {date} · 24 сағатта: {total} ішінен {n}"],
    ["Последнее наблюдение: {date} · за 24 ч: {n} из {total} · есть данные прежних дат", "Last observed: {date} · past 24 h: {n} of {total} · includes earlier dates", "Соңғы бақылау: {date} · 24 сағатта: {total} ішінен {n} · бұрынғы күндердің деректері бар"],
    ["Цена квартиры ÷ площадь · n={n}. Группы менее 5 объектов без медианы.", "Apartment price ÷ area · n={n}. Groups under 5 have no median.", "Пәтер бағасы ÷ ауданы · n={n}. 5 нысаннан аз топтарда медиана жоқ."],
    ["Цена дома с участком ÷ площадь участка · n={n}. Группы менее 5 объектов без медианы.", "House and plot price ÷ plot area · n={n}. Groups under 5 have no median.", "Үй мен жер бағасы ÷ жер аумағы · n={n}. 5 нысаннан аз топтарда медиана жоқ."],
    ["{n} за 1 {unit}", "{n} per {unit}", "1 {unit} үшін {n}"],
    ["Показать ещё 100 из {n}", "Show 100 more of {n}", "{n} ішінен тағы 100 көрсету"],
    ["Подробнее об объекте № {id}", "Details for property № {id}", "№ {id} нысан туралы толығырақ"],
    ["Координаты: {lat}, {lon}", "Coordinates: {lat}, {lon}", "Координаталар: {lat}, {lon}"],
    ["Изменений цены: {n}", "Price changes: {n}", "Баға өзгерісі: {n}"],
    ["Продавец: {name}", "Seller: {name}", "Сатушы: {name}"],
    ["Полигон: {n} {word}. Можно сохранить или изменить.", "Polygon: {n} points. Save or edit it.", "Полигон: {n} нүкте. Сақтауға немесе өзгертуге болады."],
    ["Отмечено вершин: {n}. После третьей сохраните область.", "Points marked: {n}. Save the area after the third.", "Белгіленген нүкте: {n}. Үшіншіден кейін аумақты сақтаңыз."],
    ["Активная область: {bounds}", "Active area: {bounds}", "Белсенді аумақ: {bounds}"],
    ["Активный полигон: {n} {word}. Охватывающий прямоугольник: {bounds}", "Active polygon: {n} points. Bounding rectangle: {bounds}", "Белсенді полигон: {n} нүкте. Қамтушы тікбұрыш: {bounds}"],
    ["Полигон · {n} {word}", "Polygon · {n} points", "Полигон · {n} нүкте"],
    ["В каталоге {n} {word} без координат: их принадлежность области неизвестна.", "{n} catalog listings have no coordinates; their area membership is unknown.", "Каталогтағы {n} хабарландырудың координатасы жоқ; аумаққа қатысы белгісіз."],
    ["{file}: файл больше 15 МБ.", "{file}: file exceeds 15 MB.", "{file}: файл 15 МБ-тан үлкен."],
    ["Загружено {n} демонстрационных объекта. Это вымышленные данные.", "Loaded {n} demo properties. These are fictional data.", "{n} демо нысан жүктелді. Бұл ойдан шығарылған деректер."],
    ["Добавлено или обновлено: {n}. Файлов: {files}.", "Added or updated: {n}. Files: {files}.", "Қосылды немесе жаңартылды: {n}. Файлдар: {files}."],
    ["Импортировано {n} карточек из {files} HTML-файлов в SQLite.", "Imported {n} listings from {files} HTML files into SQLite.", "{files} HTML файлынан {n} хабарландыру SQLite-қа импортталды."],
    ["Экспортировано {n} {word} из SQLite. Учтены текущая область и фильтры.", "Exported {n} listings from SQLite. Current area and filters applied.", "SQLite-тан {n} хабарландыру экспортталды. Ағымдағы аумақ пен сүзгілер ескерілді."],
    ["Экспортировано {n} {word} из {total}. Учтены текущая область и фильтры каталога.", "Exported {n} of {total} listings. Current area and catalog filters applied.", "{total} ішінен {n} хабарландыру экспортталды. Ағымдағы аумақ пен каталог сүзгілері ескерілді."],
    ["{n} новых стр.", "{n} new pages", "{n} жаңа бет"],
    ["{n} стр.", "{n} pages", "{n} бет"],
    ["{n} с точкой", "{n} with coordinates", "{n} координатасы бар"],
    ["{n} без точки", "{n} without coordinates", "{n} координатасыз"],
    ["{n} вне области", "{n} outside area", "{n} аумақтан тыс"],
    ["{n} другой адрес", "{n} address mismatches", "{n} мекенжай сәйкес емес"],
    ["до {n} стр.", "up to {n} pages", "{n} бетке дейін"],
    ["Источник снимка: {date}", "Snapshot source: {date}", "Көшірме дереккөзі: {date}"],
    ["по названию: {name}", "by name: {name}", "атауы бойынша: {name}"],
    ["{n} объявление", "{n} listings", "{n} хабарландыру"],
    ["{n} объявления", "{n} listings", "{n} хабарландыру"],
    ["{n} объявлений", "{n} listings", "{n} хабарландыру"],
    ["{date} · {n} {word} в том импорте.", "{date} · {n} listings in that import.", "{date} · сол импортта {n} хабарландыру."],
    ["Попытка {date} · 0 новых страниц. Снимок от {cached}: {n} {word} в том запросе.", "Attempt {date} · 0 new pages. Snapshot from {cached}: {n} listings in that request.", "Әрекет {date} · 0 жаңа бет. {cached} күнгі көшірме: сол сұрауда {n} хабарландыру."],
    ["Попытка {date} · HTTP {status} · 0 новых страниц. Снимок от {cached}: {n} {word} в том запросе.", "Attempt {date} · HTTP {status} · 0 new pages. Snapshot from {cached}: {n} listings in that request.", "Әрекет {date} · HTTP {status} · 0 жаңа бет. {cached} күнгі көшірме: сол сұрауда {n} хабарландыру."],
    ["{date} · {pages} новых стр. · {n} {word} в том запросе.", "{date} · {pages} new pages · {n} listings in that request.", "{date} · {pages} жаңа бет · сол сұрауда {n} хабарландыру."],
    ["{date} · {pages} новых стр. · {n} {word} в том запросе · HTTP {status}.", "{date} · {pages} new pages · {n} listings in that request · HTTP {status}.", "{date} · {pages} жаңа бет · сол сұрауда {n} хабарландыру · HTTP {status}."],
    ["Данные браузера · пакет {n} {word}", "Browser data · batch of {n} listings", "Браузер деректері · {n} хабарландыру пакеті"],
    ["После {reason} запрос отложен до {date}.", "After {reason}, the request is deferred until {date}.", "{reason} себебінен сұрау {date} дейін кейінге қалдырылды."],
    ["После {reason} новый запрос отложен до {date}. Сохранённые карточки остаются в каталоге.", "After {reason}, a new request is deferred until {date}. Saved listings remain in the catalog.", "{reason} себебінен жаңа сұрау {date} дейін кейінге қалдырылды. Сақталған хабарландырулар каталогта қалады."],
    ["Не удалось открыть локальную базу: {error}", "Could not open local database: {error}", "Жергілікті дерекқорды ашу мүмкін болмады: {error}"],
    ["Каталог открыт из SQLite. Перенос прежних данных браузера не завершён: {error}", "Catalog opened from SQLite. Earlier browser data migration failed: {error}", "Каталог SQLite-тан ашылды. Бұрынғы браузер деректерін көшіру аяқталмады: {error}"],
    ["Krisha.kz вернул страницу проверки доступа (HTTP {status}). Новая выдача не получена. Для стабильного автоматического сбора нужна настройка доступа со стороны Kolesa.", "Krisha.kz returned an access check page (HTTP {status}). No new results were received. Stable automated collection requires access setup with Kolesa.", "Krisha.kz қолжетімділікті тексеру бетін қайтарды (HTTP {status}). Жаңа нәтижелер алынбады. Тұрақты автоматты жинау үшін Kolesa тарапынан қолжетімділікті баптау қажет."],
    ["Krisha.kz отклонил запрос выдачи (HTTP {status}). Сбор остановлен. Попробуйте позже; если ошибка повторяется, уточните у Kolesa технические условия доступа.", "Krisha.kz rejected the results request (HTTP {status}). Collection stopped. Try later; if this repeats, ask Kolesa about access conditions.", "Krisha.kz нәтижелер сұрауын қабылдамады (HTTP {status}). Жинау тоқтады. Кейінірек көріңіз; қате қайталанса, Kolesa компаниясынан қолжетімділік шарттарын нақтылаңыз."],
    ["Krisha.kz вернул HTTP {status}; сбор остановлен.", "Krisha.kz returned HTTP {status}; collection stopped.", "Krisha.kz HTTP {status} қайтарды; жинау тоқтады."],
    ["Не удалось получить страницу выдачи: {error}", "Could not load the results page: {error}", "Нәтижелер бетін жүктеу мүмкін болмады: {error}"],
    ["Не удалось получить координаты: {error}", "Could not load coordinates: {error}", "Координаталарды алу мүмкін болмады: {error}"],
    ["Карта вернула HTTP {status}", "Map returned HTTP {status}", "Карта HTTP {status} қайтарды"],
    ["Krisha.kz вернул HTTP {status}", "Krisha.kz returned HTTP {status}", "Krisha.kz HTTP {status} қайтарды"],
    ["Krisha.kz вернул HTTP {status}.", "Krisha.kz returned HTTP {status}.", "Krisha.kz HTTP {status} қайтарды."],
    ["Собрано {n} {word} на {pages} {pageword}; с координатами — {geo}.", "Collected {n} listings over {pages} pages; {geo} with coordinates.", "{pages} беттен {n} хабарландыру жиналды; {geo} координатасы бар."],
    ["Вне области: {n}; без координат: {missing}.", "Outside area: {n}; without coordinates: {missing}.", "Аумақтан тыс: {n}; координатасыз: {missing}."],
    ["По адресу не подошли: {n}.", "Address mismatches: {n}.", "Мекенжайы сәйкес емес: {n}."],
    ["Ошибки карты: {errors}", "Map errors: {errors}", "Карта қателері: {errors}"],
    ["Снимок от {date}: {n} {word}. Новые объявления и цены не проверены.", "Snapshot from {date}: {n} listings. New listings and prices were not checked.", "{date} күнгі көшірме: {n} хабарландыру. Жаңа хабарландырулар мен бағалар тексерілмеді."],
    ["До остановки собрано {n} {word} на {pages} страницах. Выдача неполная; данные сохранены в SQLite.", "Before stopping, {n} listings were collected over {pages} pages. Results are incomplete; data was saved to SQLite.", "Тоқтағанға дейін {pages} беттен {n} хабарландыру жиналды. Нәтиже толық емес; деректер SQLite-та сақталды."],
    ["{reason} Ранее сохранённые карточки остаются в каталоге.", "{reason} Previously saved listings remain in the catalog.", "{reason} Бұрын сақталған хабарландырулар каталогта қалады."]
  ];
  const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const compiled = templates.map((entry) => {
    const names = [];
    const source = entry[0].replace(/\{([a-z]+)\}/g, (_, name) => { names.push(name); return `\u0000${names.length - 1}\u0000`; });
    const parts = source.split(/\u0000(\d+)\u0000/);
    const numeric = "([\\d\\s.,+₸\\u00a0]+)";
    const variable = { n: numeric, total: numeric, pages: numeric, geo: numeric, missing: numeric,
      status: "(\\d+)", word: "([\\p{L}-]+)", pageword: "([\\p{L}-]+)",
      lat: "([-\\d.]+)", lon: "([-\\d.]+)", bounds: "([\\d.,-]+)" };
    const pattern = parts.map((part, index) => index % 2 ? (variable[names[Number(part)]] || "(.+?)") : escapeRegExp(part)).join("");
    return { names, regex: new RegExp(`^${pattern}$`, "u"), en: entry[1], kk: entry[2] };
  });
  const originals = new WeakMap();
  const attributes = new WeakMap();
  const originalTitle = document.title;
  const originalDescription = document.querySelector('meta[name="description"]')?.content || "";
  let language;
  try { language = localStorage.getItem(STORAGE_KEY) || "ru"; } catch { language = "ru"; }
  if (!(language in locales)) language = "ru";

  function translate(value, lang = language) {
    if (lang === "ru") return value;
    const direct = messages[value];
    if (direct) return direct[lang === "en" ? 0 : 1];
    for (const entry of compiled) {
      const match = value.match(entry.regex);
      if (!match) continue;
      const args = Object.fromEntries(entry.names.map((name, index) => [name, match[index + 1]]));
      return entry[lang].replace(/\{([a-z]+)\}/g, (_, name) => args[name] ?? "");
    }
    return value;
  }

  function translateNode(node) {
    if (node.parentElement?.closest("script, style, code, pre, textarea, .object-title, .address-cell, .place-suggestion, #map-card-content strong")) return;
    const previous = originals.get(node);
    const current = node.nodeValue;
    const source = previous && previous.rendered === current ? previous.source : current;
    const trimmed = source.trim();
    if (!trimmed) return;
    const replacement = translate(trimmed);
    const rendered = source.replace(trimmed, replacement);
    originals.set(node, { source, rendered });
    if (current !== rendered) node.nodeValue = rendered;
  }

  function translateAttributes(element) {
    let state = attributes.get(element);
    if (!state) { state = {}; attributes.set(element, state); }
    for (const name of ["placeholder", "aria-label", "title", "content"]) {
      if (!element.hasAttribute(name)) continue;
      const current = element.getAttribute(name);
      const previous = state[name];
      const source = previous && previous.rendered === current ? previous.source : current;
      const rendered = translate(source);
      state[name] = { source, rendered };
      if (current !== rendered) element.setAttribute(name, rendered);
    }
  }

  function translateTree(root = document.body) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) { translateNode(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    translateAttributes(root);
    for (const element of root.querySelectorAll("*")) translateAttributes(element);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) translateNode(node);
    document.documentElement.lang = language === "kk" ? "kk" : language;
    document.title = translate(originalTitle);
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = translate(originalDescription);
    for (const button of document.querySelectorAll("[data-lang]")) button.setAttribute("aria-pressed", String(button.dataset.lang === language));
    for (const option of document.querySelectorAll("#live-city option")) {
      const labels = cityLabels[option.value];
      if (labels) {
        const label = labels[language === "en" ? 1 : language === "kk" ? 2 : 0];
        if (option.textContent !== label) option.textContent = label;
      }
    }
    for (const link of document.querySelectorAll("a[data-openapi]")) link.href = language === "ru" ? "openapi.json" : `openapi.${language}.json`;
    for (const link of document.querySelectorAll("a[data-docs]")) link.href = `https://github.com/archsh1d/krisha-list/blob/main/README${language === "ru" ? "" : "." + language}.md`;
  }

  function setLanguage(next) {
    if (!(next in locales) || next === language) return;
    language = next;
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* Browsers may block storage. */ }
    document.documentElement.classList.add("language-transition");
    window.dispatchEvent(new CustomEvent("languagechange", { detail: { language: next } }));
    translateTree();
    window.setTimeout(() => document.documentElement.classList.remove("language-transition"), 320);
  }

  window.KrishaI18n = { get language() { return language; }, locale: () => locales[language], translate, refresh: translateTree, setLanguage };
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-lang]");
    if (button) setLanguage(button.dataset.lang);
  });
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "attributes") translateAttributes(record.target);
      else if (record.type === "characterData") translateNode(record.target);
      else for (const node of record.addedNodes) translateTree(node);
    }
  });
  observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["placeholder", "aria-label", "title"] });
  translateTree();
})();
