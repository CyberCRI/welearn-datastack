import logging
import re

logger = logging.getLogger(__name__)

STOP_WORDS_EN = set(
    """
a about above across after afterwards again against all almost alone along
already also although always am among amongst amount an and another any anyhow
anyone anything anyway anywhere are around as at

back be became because become becomes becoming been before beforehand behind
being below beside besides between beyond both bottom but by

call can cannot ca could

did do does doing done down due during

each eight either eleven else elsewhere empty enough even ever every
everyone everything everywhere except

few fifteen fifty first five for former formerly forty four from front full
further

get give go

had has have he hence her here hereafter hereby herein hereupon hers herself
him himself his how however hundred

i if in indeed into is it its itself

keep

last latter latterly least less

just

made make many may me meanwhile might mine more moreover most mostly move much
must my myself

name namely neither never nevertheless next nine no nobody none noone nor not
nothing now nowhere

of off often on once one only onto or other others otherwise our ours ourselves
out over own

part per perhaps please put

quite

rather re really regarding

same say see seem seemed seeming seems serious several she should show side
since six sixty so some somehow someone something sometime sometimes somewhere
still such

take ten than that the their them themselves then thence there thereafter
thereby therefore therein thereupon these they third this those though three
through throughout thru thus to together too top toward towards twelve twenty
two

under until up unless upon us used using

various very very via was we well were what whatever when whence whenever where
whereafter whereas whereby wherein whereupon wherever whether which while
whither who whoever whole whom whose why will with within without would

yet you your yours yourself yourselves
""".split()
)  # Taken from spaCy

STOP_WORDS_FR = set(
    """
a à â abord afin ah ai aie ainsi ait allaient allons
alors anterieur anterieure anterieures antérieur antérieure antérieures
apres après as assez attendu au
aupres auquel aura auraient aurait auront
aussi autre autrement autres autrui aux auxquelles auxquels avaient
avais avait avant avec avoir avons ayant

bas basee bat

c' c’ ça car ce ceci cela celle celle-ci celle-la celle-là celles celles-ci celles-la celles-là
celui celui-ci celui-la celui-là cent cependant certain certaine certaines certains certes ces
cet cette ceux ceux-ci ceux-là chacun chacune chaque chez ci cinq cinquantaine cinquante
cinquantième cinquième combien comme comment compris concernant

d' d’ da dans de debout dedans dehors deja dejà delà depuis derriere
derrière des desormais desquelles desquels dessous dessus deux deuxième
deuxièmement devant devers devra different differente differentes differents différent
différente différentes différents dire directe directement dit dite dits divers
diverse diverses dix dix-huit dix-neuf dix-sept dixième doit doivent donc dont
douze douzième du duquel durant dès déja déjà désormais

effet egalement eh elle elle-meme elle-même elles elles-memes elles-mêmes en encore
enfin entre envers environ es ès est et etaient étaient etais étais etait était
etant étant etc etre être eu eux eux-mêmes exactement excepté également

fais faisaient faisant fait facon façon feront font

gens

ha hem hep hi ho hormis hors hou houp hue hui huit huitième
hé i il ils importe

j' j’ je jusqu jusque juste

l' l’ la laisser laquelle le lequel les lesquelles lesquels leur leurs longtemps
lors lorsque lui lui-meme lui-même là lès

m' m’ ma maint maintenant mais malgre malgré me meme memes merci mes mien
mienne miennes miens mille moi moi-meme moi-même moindres moins
mon même mêmes

n' n’ na ne neanmoins neuvième ni nombreuses nombreux nos notamment
notre nous nous-mêmes nouveau nul néanmoins nôtre nôtres

o ô on ont onze onzième or ou ouias ouste outre
ouvert ouverte ouverts où

par parce parfois parle parlent parler parmi partant
pas pendant pense permet personne peu peut peuvent peux plus
plusieurs plutot plutôt possible possibles pour pourquoi
pourrais pourrait pouvait prealable precisement
premier première premièrement
pres procedant proche près préalable précisement pu puis puisque

qu' qu’ quand quant quant-à-soi quarante quatorze quatre quatre-vingt
quatrième quatrièmement que quel quelconque quelle quelles quelqu'un quelque
quelques quels qui quiconque quinze quoi quoique

relative relativement rend rendre restant reste
restent retour revoici revoila revoilà

s' s’ sa sait sans sauf se seize selon semblable semblaient
semble semblent sent sept septième sera seraient serait seront ses seul seule
seulement seuls seules si sien sienne siennes siens sinon six sixième soi soi-meme soi-même soit
soixante son sont sous souvent specifique specifiques spécifique spécifiques stop
suffisant suffisante suffit suis suit suivant suivante
suivantes suivants suivre sur surtout

t' t’ ta tant te tel telle tellement telles tels tenant tend tenir tente
tes tien tienne tiennes tiens toi toi-meme toi-même ton touchant toujours tous
tout toute toutes treize trente tres trois troisième troisièmement très
tu té

un une unes uns

va vais vas vers via vingt voici voila voilà vont vos
votre votres vous vous-mêmes vu vé vôtre vôtres

y

""".split()
)  # Taken from spaCy

STOP_WORDS_ES = set(
    """
a acuerdo adelante ademas además afirmó agregó ahi ahora ahí al algo alguna
algunas alguno algunos algún alli allí alrededor ambos ante anterior antes
apenas aproximadamente aquel aquella aquellas aquello aquellos aqui aquél
aquélla aquéllas aquéllos aquí arriba aseguró asi así atras aun aunque añadió
aún

bajo bastante bien breve buen buena buenas bueno buenos

cada casi cierta ciertas cierto ciertos cinco claro comentó como con conmigo
conocer conseguimos conseguir considera consideró consigo consigue consiguen
consigues contigo contra creo cual cuales cualquier cuando cuanta cuantas
cuanto cuantos cuatro cuenta cuál cuáles cuándo cuánta cuántas cuánto cuántos
cómo

da dado dan dar de debajo debe deben debido decir dejó del delante demasiado
demás dentro deprisa desde despacio despues después detras detrás dia dias dice
dicen dicho dieron diez diferente diferentes dijeron dijo dio doce donde dos
durante día días dónde

e el ella ellas ello ellos embargo en encima encuentra enfrente enseguida
entonces entre era eramos eran eras eres es esa esas ese eso esos esta estaba
estaban estado estados estais estamos estan estar estará estas este esto estos
estoy estuvo está están excepto existe existen explicó expresó él ésa ésas ése
ésos ésta éstas éste éstos

fin final fue fuera fueron fui fuimos

gran grande grandes

ha haber habia habla hablan habrá había habían hace haceis hacemos hacen hacer
hacerlo haces hacia haciendo hago han hasta hay haya he hecho hemos hicieron
hizo hoy hubo

igual incluso indicó informo informó ir

junto

la lado largo las le les llegó lleva llevar lo los luego

mal manera manifestó mas mayor me mediante medio mejor mencionó menos menudo mi
mia mias mientras mio mios mis misma mismas mismo mismos modo mucha muchas
mucho muchos muy más mí mía mías mío míos

nada nadie ni ninguna ningunas ninguno ningunos ningún no nos nosotras nosotros
nuestra nuestras nuestro nuestros nueva nuevas nueve nuevo nuevos nunca

o ocho once os otra otras otro otros

para parece parte partir pasada pasado paìs peor pero pesar poca pocas poco
pocos podeis podemos poder podria podriais podriamos podrian podrias podrá
podrán podría podrían poner por porque posible primer primera primero primeros
pronto propia propias propio propios proximo próximo próximos pudo pueda puede
pueden puedo pues

qeu que quedó queremos quien quienes quiere quiza quizas quizá quizás quién
quiénes qué

realizado realizar realizó repente respecto

sabe sabeis sabemos saben saber sabes salvo se sea sean segun segunda segundo
según seis ser sera será serán sería señaló si sido siempre siendo siete sigue
siguiente sin sino sobre sois sola solamente solas solo solos somos son soy su
supuesto sus suya suyas suyo suyos sé sí sólo

tal tambien también tampoco tan tanto tarde te temprano tendrá tendrán teneis
tenemos tener tenga tengo tenido tenía tercera tercero ti tiene tienen toda
todas todavia todavía todo todos total tras trata través tres tu tus tuvo tuya
tuyas tuyo tuyos tú

u ultimo un una unas uno unos usa usais usamos usan usar usas uso usted ustedes
última últimas último últimos

va vais vamos van varias varios vaya veces ver verdad verdadera verdadero vez
vosotras vosotros voy vuestra vuestras vuestro vuestros

y ya yo
""".split()
)  # Taken from spaCy

STOPWORDS = {
    "en": STOP_WORDS_EN,
    "fr": STOP_WORDS_FR,
    "es": STOP_WORDS_ES,
}


def tokenize(text, lang="en"):
    """
    Tokenize input text into words and punctuation, remove stopwords for the given language.
    Supported languages for stopword removal: 'en', 'fr', 'es'
    """
    # Regex matches for multilingual word boundaries, numbers, and punctuation
    # \w matches Unicode word chars if re.UNICODE (default in Python 3)
    pattern = r"""(?x)
        (?:[A-Za-zÀ-ÿ]\.)+      # Abbreviations, e.g. U.S.A., É.U.
      | \w+(?:[-’']\w+)*        # Words with optional hyphens or apostrophes (multilingual)
      | \d+\.\d+                # Numbers with a decimal point
      | \d+                     # Numbers
      | \.\.\.                  # Ellipsis
      | [.,!?;:()"\[\]{}'`’“”¿¡«»] # Punctuation (incl. Spanish/French)
    """
    tokens = re.findall(pattern, text)
    stopwords = STOPWORDS.get(lang, set())

    # Remove stopwords (case-insensitive, but keep original token case)
    filtered_tokens = [tok for tok in tokens if tok.lower() not in stopwords]
    return filtered_tokens
