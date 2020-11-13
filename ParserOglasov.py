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
# TODO: še analiza cen (povprečna cena / mediana [ker outlayerji]) + možnost da se določene za trajno izloči (ker oglas za nekaj drugega)

import requests
import bs4
import sys
import shelve
import os
import copy
import datetime
import dateutil.parser
import pprint
import ezgmail

# ta url lahko tu spremeniš v poljubni search term (po keywords=)
baseUrl ='https://www.bolha.com/?ctl=search_ads&keywords='
query = 'oculus+quest'
url = baseUrl+query
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

        # ustvari dict objektov oglasov:
        for naslov, cena, id_, objava in zip(naslovi, cene, idji, objave):
            dictObjektovProduktov[id_] = Produkt(
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
    storage = shelve.open('./userData/'+query)
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
            poljaZaIzpis = [           str(produkt.cenaZadnja)[:4].ljust(4),
                            ' || ',        produkt.naslov[:38].ljust(40,'_'),
                            ' || ŠE:', str(doPoteka).rjust(2),
                            #' || DO:', f'{produkt.potek:%Y-%m-%d}',
                            ' || STATUS:', produkt.status
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

def logirajSpremembe(spremembe):
    print('\n(logiram spremembe v file: /userData/'+query+'-log.txt)')
    with open('./userData/'+query+'-log.txt','a') as log:
        log.write('\n'+str(datetime.date.today())+':\n')
        for line in spremembe:
            log.write(line+'\n')
        #log.writelines(str(datetime.date.today)+': \n'+spremembe+'\n')

def primerjajCene(stariOglasi: dict, noviOglasi: dict, aliPosljeMail = False) -> list,dict:
    """Primerja stare in nove oglase in izpiše spremembe. Ter pošlje mail o spremembah, če argument 'aliPosljeMail'=True
    Vrne list sprememb in updatan list vseh oglasov"""
    print('\nSPREMEMBE PRI OGLASIH')
    spremembe = []
    # historyOglasi = copy.deepcopy(stariOglasi)        # to je za zgodovino sprememb oglasov

    # preveri, če vsi stari še tu in če se kaj spremenili:
    for stariId, stariProdukt in stariOglasi.items():
        
        # najprej spremeni status 'novih' v 'aktivne' če že minilo 2 dni:       # a bi blo to bolj primerno kje drugje?
        if (stariProdukt.status == 'novi') and (stariProdukt.objava + datetime.timedelta(days=2)) < datetime.datetime.now(datetime.timezone.utc):
            stariProdukt.status = 'aktiven'
        
        #I.) AKTIVNI OGLASI:
        if stariProdukt.status in ['aktiven','novi']:
            # I.1.) aktivnega oglasa ni več:
            if (stariId not in noviOglasi):
                # I.1.a) aktivnega oglasa ni več, ker oglas potekel:
                if datetime.datetime.now(datetime.timezone.utc) > stariProdukt.potek:
                    sporocilo = f'---{stariProdukt.naslov}\n   (oglas je potekel - zadnja cena: {stariProdukt.cenaZadnja}€)'
                    spremembe.append(sporocilo)
                    stariProdukt.status = 'potekel'
                    #historyOglasi[stariId].status = 'potekel'

                # I.1.b) aktivnega oglasa ni več, ker izdelek prodan:
                if datetime.datetime.now(datetime.timezone.utc) < stariProdukt.potek:
                    sporocilo = f'---{stariProdukt.naslov}\n   (izdelek prodan - zadnja cena: {stariProdukt.cenaZadnja}€)'
                    spremembe.append(sporocilo)
                    stariProdukt.status = 'prodan'
                    #historyOglasi[stariId].status = 'prodan'

            # I.2.) aktivni oglas še vedno obstaja:
            elif stariId in noviOglasi:
                # I.2.a) oglas aktiven, a spremenjena cena:
                if stariProdukt.cenaZadnja != noviOglasi[stariId].cenaZadnja:
                    sporocilo = f"---{stariProdukt.naslov} \n   (sprememba cene: {stariProdukt.cenaZadnja}€ >> {noviOglasi[stariId].cenaZadnja}€)"
                    spremembe.append(sporocilo)
                    stariProdukt.cenaZadnja = noviOglasi[stariId].cenaZadnja
                    #historyOglasi[stariId].cenaZadnja = noviOglasi[stariId].cenaZadnja
                # I.2.b) oglas aktiven in enak
                else:
                    #print(f'---{stariId}: ni spremembe')
                    pass
            else:
                print('NAPAKA - stari oglas niti ni v novih oglasih niti je - wtf?')
            
            # v vsakem primeru pa tudi updataj history sprememb
            # ...koda...

        # I.) NEAKTIVNI OGLASI
        """ if (stariProdukt.status in ['prodan','potekel']) and (stariId in noviOglasi):
            sporocilo = f"---{stariProdukt.naslov}, \n   (potekli oglas se je znova pojavil! {stariProdukt.cenaZadnja}€ >> {noviOglasi[stariId].cenaZadnja}€)"
                spremembe.append(sporocilo)
                stariProdukt.status = 'aktiven' # ???? """

    # preveri, če kak nov oglas, ki ga ni bilo pri starih
    for noviId, noviProdukt in noviOglasi.items():
        # 3.) nov oglas
        if noviId not in stariOglasi:
            sporocilo = f'---{noviProdukt.naslov}; {noviProdukt.cenaZadnja}€\n   (to je nov oglas!)'
            spremembe.append(sporocilo)
            stariOglasi[noviId] = noviProdukt
            stariOglasi[noviId].status = 'novi'
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
        storage = shelve.open('./userData/'+query)
        
        if (aliPosljeMail == True) and ('aliPosiljaMaile' in storage.keys()) and (storage['aliPosiljaMaile'] == True):
            izpisNovihOglasov = getStringOglasov(noviOglasi)
            teloMaila = stringVsehSprememb+izpisNovihOglasov+'\n\nLink do oglasov na Bolhi: \n'+url    # pazi, to je global var
            posljiMail('Spremembe na Bolhi!',teloMaila)


        # TODO: if input('Ali želiš pogledati stran na bolhi? ( Y+[enter] za yes // [enter] za preskoči') in (y,Y):
    return spremembe, stariOglasi

def mockSpreminjanjeCen():
    print ('Mock spreminjam par oglasov')
    try:
        del(noviOglasi['4892108'])
    except:
        print ('Nisem mogel mock zbrisat enega oglasa - očitno ne obstaja več)
    try:
        noviOglasi['111111'] = Produkt(
        'avtobus', "77", '111111', datetime.datetime.now(datetime.timezone.utc), {})
    except:
        print ('Nisem mogel mock dodat novega oglasa - očitno rabi dodatne nove attribute')
    try:
        noviOglasi['4983459'].cenaZadnja = 50
    except:
        print ('Nisem mogel mock spremenit cene pri enem oglasu - očitno ne obstaja več')


def shraniNoveCeneVStorage(noviOglasi: dict):
    # if input("\nZa shranitev novih oglasov pritisni Y+[enter] // ali pa preskoči z [enter]: ") in ['y', 'Y']:
    storage = shelve.open('./userData/'+query)
    storage['oglasi'] = noviOglasi
    storage.close()
    print('\n(shranil nove oglase v storage)')


def posljiMail(subject, telo):
    storage = shelve.open('./userData/'+query)
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


def nastavitveMaila():
    print ('\nNASTAVITVE POŠILJANJA NA MAIL:')
    storage = shelve.open('./userData/'+query)
    # preveri, ali je pošiljanje mailov vklopljeno:
    if 'aliPosiljaMaile' not in storage.keys(): # (če še nikdar nastavljeno)
        storage['aliPosiljaMaile'] = False
    
    if storage['aliPosiljaMaile'] == False:
        print('Pošiljanje email obvestil o spremembah je IZKLOPLJENO.')
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
mockSpreminjanjeCen()
spremembe, updatedOglasi = primerjajCene(stariOglasi, noviOglasi, True)   # ce zelis programersko izklopit možnost posiljanja mailov, naj bo 3. argument=False 
sprintajOglase(updatedOglasi)
logirajSpremembe(spremembe)
#shraniNoveCeneVStorage(noviOglasi)
nastavitveMaila()


