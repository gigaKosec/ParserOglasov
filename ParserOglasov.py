#! python3
# OPIS: program parsa cene na Bolhi za določen item (oz search term - tu: oculus quest), in sporoči, če prišlo do sprememb (cen ali če kak item ne obstaja več)
# pozor: za pošiljanje mailov uporablja modul EZGmail - tega je treba instalati s pip + potrebuje določene nastavitve na gmail accountu (da ta lahko pošilja maile)
# BUG mali: ko pošlje stringOglasov gmailu ("tabela" iz stringov), se tabela "podere", ker font v gmailu nima enake širine vseh znakov
# TODO: zanekrat parsa le eno stran oglasov >> naj pregleda še ostale
# TODO: beleži zgodovino sprememb oglasov (ne le trenutno stanje vs nazadnje)
# TODO: trenutno vsaka funkcija, ki rabi storage, znova odpre in zapre storage >> iz storage-a poberi na začetku, kar rabiš
# TODO: ko program prvič zagnan, problem ker ni določenih keyev v storage-u (npr za nastavitve mail pošiljanja) >> na začetku preveri, če jih ni, in ustvari default vrednosti
# TODO: kaj če se spremeni ime oglasa (naj primarno primerja ID-je, ne naslove)
# TODO: pri datetime.now() moram stalno pisat še timezone, ker je ta prisotna, ko parsa z neta - tam jo moraš skenslat (z ignoretz = True - ampak nekaj ni delalo)
# TODO: spremeni (razširi), da lahko poljubni search term (naj naredi objekt za vsak search term)
# TODO: spremeni (razširi), da lahko tudi poljubni iskalnik (ne le Bolha) >> torej da so selektorji atributi objekta za posamezen iskalnik )
# TODO: še analiza cen (povrprečna cena / mediana [ker outlayerji]) + možnost da se določene za trajno izloči (ker oglas za nekaj drugega)

import requests
import bs4
import sys
import shelve
import os
import datetime
import dateutil.parser
import pprint
import ezgmail

# ta url lahko tu spremeniš v poljubni search term (po keywords=)
url = 'https://www.bolha.com/?ctl=search_ads&keywords=bukova+drva'
headers = {
    'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0'}
#email = 'youremailaddres@gmail.com' # spremeni v email naslov, kamor naj pošilja obvestila o spremembah ()
#page = requests.get(url, headers)
#soup = bs4.BeautifulSoup(page.content, 'html.parser')
selektorji = {
    'naslov': '.EntityList--Standard .EntityList-item .entity-title',
    'cena': '.EntityList--Standard .EntityList-item .price',
    'id_': '.EntityList--Standard .EntityList-item .entity-title a',
    'objava': '.EntityList--Standard .EntityList-item .entity-pub-date .date',
    'nextPage': '.Pagination-item--next a'
}
#nextPageLink = extractAttributValuesFromSoup(selektorji['nextPage'], 'href')[0])


class Produkt:
    def __init__(self, naslov, cenaZadnja, id_, objava, zgodovinaCen):
        self.naslov = naslov
        self.cenaZadnja = cenaZadnja
        self.id = id_
        self.objava = objava
        self.zgodovinaCen = {}
        self.status = 'aktiven'
        self.potek = self.objava + datetime.timedelta(days=30)

def extractTextsInElementsFromSoup(soup: object, css_selector: str) -> list:
    resultsHtml = soup.select(css_selector)
    resultsText = [i.get_text().strip() for i in resultsHtml]
    return resultsText


def extractAttributeValuesFromSoup(soup: object, css_selector: str, attr: str) -> list:
    resultsHtml = soup.select(css_selector)
    resultsAttributes = [i.get(attr).strip() for i in resultsHtml]
    return resultsAttributes



def createDictObjektovNajnovejsihProduktov(selektorji) -> dict:
    print('Pregledujem oglase na Bolhi...')
    dictObjektovProduktov = {}
    #stStrani = 1
    #stranOglasov = url+'&page='+str(stStrani)
    stranOglasov = url
    for loopNum in range (200):         # omejeno, da max možnih strani 200 - lahko povečaš
        page = requests.get(stranOglasov, headers)
        soup = bs4.BeautifulSoup(page.content, 'html.parser')
        naslovi = extractTextsInElementsFromSoup(soup,selektorji['naslov'])
        ceneZValuto = extractTextsInElementsFromSoup(soup,selektorji['cena'])
        cene = [i.rstrip(' €') for i in ceneZValuto]         #TODO: že tukaj spremeniti cene v int (toda problem, da ponekod str 'po dogovoru')
        idji = extractAttributeValuesFromSoup(soup,selektorji['id_'], 'name')
        testno = extractAttributeValuesFromSoup(soup,selektorji['objava'], 'datetime')
        objave = [dateutil.parser.parse(i) for i in extractAttributeValuesFromSoup(
            soup,selektorji['objava'], 'datetime')]
        # print('\nOBJAVE:\n'objave)

        for naslov, cena, id_, objava in zip(naslovi, cene, idji, objave):
            dictObjektovProduktov[naslov] = Produkt(
                naslov, cena, id_, objava, datetime.date.today())
        # prehod na naslednjo stran oglasov:
        nextPageLinkPathsList = extractAttributeValuesFromSoup(soup,selektorji['nextPage'], 'href')  # TODO: spremeni iskanje, da ne bo s selektorji (da najde le 1. hit)
        if len (nextPageLinkPathsList) == 0:
            return dictObjektovProduktov
        else:
            nextPageLinkPath = nextPageLinkPathsList[0]
            nextPageLink = 'https://www.bolha.com/'+ nextPageLinkPath   #TODO: spremeni za poljubni page
            stranOglasov = nextPageLink
    return dictObjektovProduktov



def getStariOglasiFromStorage(backupOglasi):
    storage = shelve.open('./userData/storage')
    #print('storage keys =', list(storage.items()))
    try:
        stariOglasi = storage['oglasi']
    except:
        print('Ker te oglase ogleduješ prvič, ne morem zaznati, če prišlo do kakih sprememb pri njih')
        stariOglasi = backupOglasi
    storage.close()
    return(stariOglasi)


def getStringOglasov(DictOglasov: dict) -> str:
    # TODO: izberi, katera polja naj izpiše
    #if input('Za izpis oglasov pritisni Y+[enter] \\ ali pa preskoči z [enter]: ') in ('y', 'Y'):
    # zip dveh tuplov zato, da pri obeh sprinta isto (brez da bi to posebej dajal v funkcijo), toda da začetni izpis (naslov) različen
    #for imeDict, DictOglasov in zip(('STARI', 'NOVI'), (stariOglasi, noviOglasi)): 
    #    print('\n'+imeDict+' OGLASI:')
    for Produkt in DictOglasov:
        vrstice = ['\nOGLASI:']
        for produkt in DictOglasov.values():
            doPoteka = (produkt.objava + datetime.timedelta(days=30) -
                        datetime.datetime.now(datetime.timezone.utc)).days
            poljaZaIzpis = [           produkt.cenaZadnja[:4].ljust(4),
                            ' || ',    produkt.naslov[:38].ljust(40,'_'),
                            ' || ŠE:', str(doPoteka).rjust(2)
                            #' || DO:', f'{produkt.potek:%Y-%m-%d}',
                            #' || STATUS:', produkt.status
                            #' || ID:', produkt.id
                            ]
            vrstica = ''.join(polje for polje in poljaZaIzpis)
            vrstice.append(vrstica)
            # print(vrstica)
        vrsticeIzpis = '\n'.join(vrstica for vrstica in vrstice)
        # print(vrsticeIzpis)
        return vrsticeIzpis


def sprintajOglase(oglasi):
    if input('\nZa izpis oglasov pritisni Y+[enter] \\ ali pa preskoči z [enter]: ') in ('y', 'Y'):
        print(getStringOglasov(oglasi))

def primerjajCene(stariOglasi: dict, noviOglasi: dict, aliPosljeMail = False):
    """Primerja stare in nove oglase in izpiše spremembe. Ter pošlje mail o spremembah, če argument 'aliPosljeMail'=True"""
    print('\nSPREMEMBE PRI OGLASIH')
    spremembe = []
    #updatedOglasi = stariOglasi        # to bo za nov feature zgodovine sprememb oglasov

    # preveri, če vsi stari še tu in če se kaj spremenili:
    # (tak local variable, ker je DictProduktov sestavljen iz {'produktObjekt.ime':produktObjekt})
    for staroIme, stariProdukt in stariOglasi.items():
        if staroIme not in noviOglasi:
            # 1.a opcija: oglasa ni več, ker oglas potekel
            # a to deluje?
            if datetime.datetime.now(datetime.timezone.utc) > stariProdukt.potek:
                sporocilo = f'---{stariProdukt.naslov}\n   (oglas je potekel - zadnja cena: {stariProdukt.cenaZadnja}€)'
                spremembe.append(sporocilo)
                #updatedOglasi[staroIme].status = 'potekel'

            # 1.b opcija: oglasa ni več, ker izdelek prodan
            if datetime.datetime.now(datetime.timezone.utc) < stariProdukt.potek:
                sporocilo = f'---{stariProdukt.naslov}\n   (izdelek prodan - zadnja cena: {stariProdukt.cenaZadnja}€)'
                spremembe.append(sporocilo)
                #updatedOglasi[staroIme].status = 'prodan'
        elif staroIme in noviOglasi:
            # 2.a opcija: oglas aktiven, a spremenjena cena
            if stariProdukt.cenaZadnja != noviOglasi[staroIme].cenaZadnja:
                sporocilo = f"---{staroIme} \n   (sprememba cene: {stariProdukt.cenaZadnja}€ >> {noviOglasi[staroIme].cenaZadnja}€)"
                spremembe.append(sporocilo)
            # 2.b opcija: oglas aktiven in enak
            else:
                #print(f'---{staroIme}: ni spremembe')
                pass
        else:
            print('NAPAKA - stari oglas niti ni v novih oglasih niti je - wtf?')

    # preveri, če kak nov oglas, ki ga ni bilo pri starih
    for novoIme in noviOglasi.keys():
        # 3. opcija: nov oglas
        if novoIme not in stariOglasi:
            sporocilo = f'---{novoIme}, {noviOglasi[novoIme].cenaZadnja}€\n   (to je nov oglas!)'
            spremembe.append(sporocilo)
        # TODO: naj preveri, če ta oglas bil že prej, a neaktiven (če ima isti ID) - zato rabiš najprej seznam neaktivnih

    # na koncu preveri, če bilo skupno kaj sprememb
    if len(spremembe) == 0:
        sporocilo = 'Ni sprememb.'
        print(sporocilo)
        #posljiMail('giga.kosec@gmail.com','Ni sprememb','Na Bolhi nič novega')

    else:
        print('Stevilo sprememb:', len(spremembe), '\n')
        stringVsehSprememb = '\n'.join(sporocilo for sporocilo in spremembe)
        print(stringVsehSprememb)
    
        # poslji mail obvestilo:
        storage = shelve.open('./userData/storage')
        
        if (aliPosljeMail == True) and ('aliPosiljaMaile' in storage.keys()) and (storage['aliPosiljaMaile'] == True):
            izpisNovihOglasov = getStringOglasov(noviOglasi)
            teloMaila = stringVsehSprememb+izpisNovihOglasov+'\n\nLink do oglasov na Bolhi: \n'+url    # pazi, to je global var
            posljiMail('Spremembe na Bolhi!',teloMaila)

        # TODO: if input('Ali želiš pogledati stran na bolhi? ( Y+[enter] za yes // [enter] za preskoči') in (y,Y):


def mockSpreminjanjeCen():
    #del(noviOglasi['Oculus Quest 128GB'])
    noviOglasi['avtodus'] = Produkt(
        'avtobus', 77, 111111, datetime.datetime.now(datetime.timezone.utc), {})
    #noviOglasi['Oculus Quest 64 GB'].cenaZadnja = 50


def shraniNoveCeneVStorage(noviOglasi: dict):
    # if input("\nZa shranitev novih oglasov pritisni Y+[enter] // ali pa preskoči z [enter]: ") in ['y', 'Y']:
    storage = shelve.open('./userData/storage')
    storage['oglasi'] = noviOglasi
    storage.close()
    print('\n(shranil nove oglase v storage)')


def posljiMail(subject, telo):
    storage = shelve.open('./userData/storage')
    try:
        mailNaslov = storage['mailNaslov']
        ezgmail.send(mailNaslov, subject, telo)
        print ('\nPoslal sem mail o spremembah!')
    # če mail ni nastavljen:
    except ezgmail.EZGmailException as gmailNapaka:
        print('\nPri poskusu pošiljanja emaila o spremembah se pojavila naslednja napaka:\n',gmailNapaka)
    except KeyError as manjkaKeyNapaka:
        print('\nEmail naslov za pošiljanje ni določen.')
    storage.close()

try:
    pass
except expression as identifier:
    pass

def nastavitveMaila():
    storage = shelve.open('./userData/storage')
    # preveri, ali je pošiljanje mailov vklopljeno:
    if 'aliPosiljaMaile' not in storage.keys(): # (če še nikdar nastavljeno)
        storage['aliPosiljaMaile'] = False
    
    if storage['aliPosiljaMaile'] == False:
        print('pošiljanje email obvestil o spremembah je IZKLOPLJENO.')
    elif storage['aliPosiljaMaile'] == True:
        print ('Pošiljanje email obvestil o spremembah je VKLOPLJENO.')
    try:
        mailNaslov = storage['mailNaslov']
        print ('Naslov za pošiljanje je:',mailNaslov)
    except:
        print('Naslov za pošiljanje ni nastavljen')
    # za spreminjanje nastavitev pošiljanja z mailom:
    if input ('Ali želiš spremeniti nastavitve za pošiljanje? (preskoči z [enter] // spremeni z Y+[enter]): ') in ['y','Y']:
        #1. ali naj posilja:
        aliPosilja = input ('Ali naj pošilja email obvestila? (za YES pritisni Y+[enter], za NO pritisni N+[enter]: ')
        if aliPosilja in ['y','Y']:
            storage['aliPosiljaMaile'] = True
        elif aliPosilja in ['n','N']:
            storage['aliPosiljaMaile'] = False
        
        #2. na kateri naslov naj posilja:
        try:
            mailNaslov = storage['mailNaslov']
            noviMailNaslov = input(f'Vnesi nov naslov za pošiljanje (ali pa pusti prazno, da obdržiš trenutni naslov ({mailNaslov}):  ')
            if noviMailNaslov != '':
                storage['mailNaslov'] = noviMailNaslov
                try:
                    print ('Mail naslov je spremenjen na:',storage['mailNaslov'])
                except:
                    print('Nov naslov ni bil vnešen.')  # exception nujen, ker če pustil uporabnik prazno, ni key-a v storage
        # če naslov ni nastavljen, nastavi novega
        except:
            noviMailNaslov = input ('Prosim, vnesi mail naslov, kamor naj pošiljam obvestila o spremembah: ') # TODO: dodaj preverjanje
            storage['mailNaslov'] = noviMailNaslov
            try:
                print ('Mail naslov je spremenjen na:',storage['mailNaslov'])
            except:
                print('novi naslov ni bil vnešen.')     # BUG: shrani prazen mail >> popravi

    storage.close()


# RUN APP
os.chdir(os.path.dirname(os.path.realpath(__file__)))
noviOglasi = createDictObjektovNajnovejsihProduktov(selektorji)
stariOglasi = getStariOglasiFromStorage(noviOglasi)
#mockSpreminjanjeCen()
primerjajCene(stariOglasi, noviOglasi, True)   # ce zelis programersko izklopit možnost posiljanja mailov, naj bo 3. argument=False 
sprintajOglase(noviOglasi)
shraniNoveCeneVStorage(noviOglasi)
nastavitveMaila()


