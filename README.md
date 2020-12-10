# ParserOglasov
Program parsa izbrane oglase na Bolha.com in obvesti o spremembah (npr. če kak nov oglas, če kakega oglasa ni več, če kake cene spremenjene) ter beleži zgodovino teh sprememb.
 
O spremembah lahko obvesti tudi preko maila (zaenkrat edino preko Gmaila).
Program za pošiljanje mailov uporablja python modul EZGmail (to je modul za preprosto pošiljanje e-pošte preko Gmaila) - tega je potrebno instalirati s pip. Potrebno pa je tudi nastaviti določene nastavitve na gmail accountu - na  strani
https://developers.google.com/gmail/api/quickstart/python je potrebno pritisniti "Enable the Gmail API" in slediti nadaljnim navodilom (potrebno je zdownloadati datoteko credentials.json in jo preimenovati v 'credentials.json', če je ime drugačno).

Priporočam, da se za program ne uporablja glavni mail uporabnika (npr. da ne bi morebitni hrošči slučajno pobrisali kak pomemben mail uporabnika).

 
