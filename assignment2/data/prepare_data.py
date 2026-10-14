"""Build the small clean files the page loads (data/raw -> data/clean).

Usage: python prepare_data.py   (needs pandas, xlrd, openpyxl)
"""
import os, re, shutil
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW, OUT = os.path.join(HERE, 'raw'), os.path.join(HERE, 'clean')
os.makedirs(OUT, exist_ok=True)

ABBR = {'New South Wales': 'NSW', 'Victoria': 'VIC', 'Queensland': 'QLD', 'South Australia': 'SA',
        'Western Australia': 'WA', 'Tasmania': 'TAS', 'Northern Territory': 'NT',
        'Australian Capital Territory': 'ACT'}
# Approximate visual centres of each state, used to place proportional symbols.
CENTRE = {'NSW': (146.9, -32.4), 'VIC': (144.2, -36.9), 'QLD': (144.6, -22.6), 'SA': (135.6, -30.2),
          'WA': (121.9, -25.8), 'TAS': (146.6, -42.1), 'NT': (133.4, -19.6), 'ACT': (149.1, -35.5)}


def save(df, name):
    df.to_csv(os.path.join(OUT, name), index=False)
    print(f'{name:28s} {len(df):5d} rows')


# ---------------------------------------------------------------- S1 FAO food balances
GROUPS = {
    'Cereals': ['Wheat and products', 'Rice and products', 'Barley and products', 'Maize and products', 'Rye and products', 'Oats', 'Millet and products', 'Sorghum and products', 'Cereals, other'],
    'Starchy roots': ['Cassava and products', 'Potatoes and products', 'Sweet potatoes', 'Yams', 'Roots, Other'],
    'Sugar': ['Sugar (Raw Equivalent)', 'Sweeteners, Other', 'Honey'],
    'Pulses': ['Beans', 'Peas', 'Pulses, Other and products'],
    'Tree nuts': ['Nuts and products'],
    'Vegetable oils': ['Soyabean Oil', 'Groundnut Oil', 'Sunflowerseed Oil', 'Rape and Mustard Oil', 'Cottonseed Oil', 'Palmkernel Oil', 'Palm Oil', 'Coconut Oil', 'Sesameseed Oil', 'Olive Oil', 'Maize Germ Oil', 'Oilcrops Oil, Other'],
    'Vegetables': ['Tomatoes and products', 'Onions', 'Vegetables, other'],
    'Fruit': ['Oranges, Mandarines', 'Lemons, Limes and products', 'Grapefruit and products', 'Citrus, Other', 'Bananas', 'Plantains', 'Apples and products', 'Pineapples and products', 'Dates', 'Grapes and products (excl wine)', 'Fruits, other'],
    'Meat': ['Bovine Meat', 'Mutton & Goat Meat', 'Pigmeat', 'Poultry Meat', 'Meat, Other'],
    'Eggs': ['Eggs'],
    'Milk & dairy': ['Milk - Excluding Butter'],
    'Fish & seafood': ['Freshwater Fish', 'Demersal Fish', 'Pelagic Fish', 'Marine Fish, Other', 'Crustaceans', 'Cephalopods', 'Molluscs, Other', 'Aquatic Animals, Others'],
}
ELEMENTS = {'Production': 'production', 'Import quantity': 'imports', 'Export quantity': 'exports',
            'Domestic supply quantity': 'domestic_use', 'Food supply quantity (kg/capita/yr)': 'kg_per_person'}

s1 = pd.read_excel(os.path.join(RAW, 's1-food-balance.xls'))
s1['Value'] = pd.to_numeric(s1['Value'], errors='coerce')
s1 = s1[s1.Element.isin(ELEMENTS)]
s1['measure'] = s1.Element.map(ELEMENTS)
inv = {i: g for g, items in GROUPS.items() for i in items}
s1['group'] = s1.Item.map(inv)

g = (s1[s1.group.notna()].pivot_table(index=['Year', 'group'], columns='measure', values='Value', aggfunc='sum')
     .reset_index().rename(columns={'Year': 'year'}))
g['self_sufficiency'] = (100 * g.production / g.domestic_use).round(1)
save(g.round(2), 'fbs_groups.csv')

# Per-person supply for the items the story follows (meat split out by animal).
ITEMS = {'Bovine Meat': 'Beef', 'Poultry Meat': 'Chicken & poultry', 'Pigmeat': 'Pork',
         'Mutton & Goat Meat': 'Lamb & mutton'}
it = s1[(s1.measure == 'kg_per_person') & s1.Item.isin(ITEMS)].assign(food=lambda d: d.Item.map(ITEMS))
grp = g[g.group.isin(['Fruit', 'Milk & dairy', 'Cereals', 'Vegetables', 'Fish & seafood'])].rename(columns={'group': 'food'})
pc = pd.concat([it[['Year', 'food', 'Value']].rename(columns={'Year': 'year', 'Value': 'kg_per_person'}),
                grp[['year', 'food', 'kg_per_person']]])
save(pc.round(2), 'fbs_per_person.csv')

# ---------------------------------------------------------------- S2 ABS apparent consumption
S2 = os.path.join(RAW, 's2-consumption.xlsx')
MONTHLY = {'Cereals and cereal products': 'Cereals (bread, flour, pasta)', 'Fruit products and dishes': 'Fruit',
           'Vegetable products and dishes': 'Vegetables', 'Milk products and dishes': 'Milk products',
           'Meat, poultry and game products and dishes': 'Meat & poultry'}
m = pd.read_excel(S2, 'Table 1.2', header=None)
hdr = m.iloc[6].tolist()
maj = m[m[0] == 'Major'].copy(); maj.columns = hdr
maj = maj[maj[hdr[2]].isin(MONTHLY)]
long = maj.melt(id_vars=hdr[:3], value_vars=hdr[3:], var_name='month', value_name='grams_per_day')
long = long[long.month.astype(str).str.match(r'^[A-Z][a-z]{2} \d{4}$')]
long['group'] = long[hdr[2]].map(MONTHLY)
long['month'] = pd.to_datetime(long.month, format='%b %Y').dt.strftime('%Y-%m')
long['grams_per_day'] = pd.to_numeric(long.grams_per_day, errors='coerce').round(1)
save(long[['month', 'group', 'grams_per_day']], 'retail_monthly.csv')

t = pd.read_excel(S2, 'Table 1.1', header=None)
FY = ['2018-19', '2019-20', '2020-21', '2021-22', '2022-23', '2023-24']
body = t[t[0].isin(['Major', 'Sub-major'])].iloc[:, :15]
body.columns = ['level', 'code', 'name'] + [f't_{y}' for y in FY] + FY
abs_g = body.set_index('code')[FY].apply(pd.to_numeric, errors='coerce')

# ---------------------------------------------------------------- Chart 8: FAO supply vs ABS sales (overlap years)
# FAO calendar 2019..2023 is aligned with ABS financial year 2018-19..2022-23 (Step 3, L8).
fao_item = s1[s1.measure == 'kg_per_person'].pivot_table(index='Item', columns='Year', values='Value')
fao_grp = g.pivot_table(index='group', columns='year', values='kg_per_person')
PAIRS = {  # label: (FAO series, ABS food-group codes)
    'Fruit': (fao_grp.loc['Fruit'], [16]),
    'Vegetables': (fao_grp.loc['Vegetables'], [24]),
    'Dairy milk': (fao_grp.loc['Milk & dairy'], [191]),
    'Chicken & poultry': (fao_item.loc['Poultry Meat'], [183]),
    'Beef, lamb & pork': (fao_item.loc[['Bovine Meat', 'Mutton & Goat Meat', 'Pigmeat']].sum(), [181]),
    'Cereals': (fao_grp.loc['Cereals'], [12]),
}
rows = []
for label, (fao, codes) in PAIRS.items():
    a = abs_g.loc[codes].sum()
    for i, yr in enumerate(range(2019, 2024)):
        rows.append({'food': label, 'year': yr, 'source': 'Food supply (FAO)', 'value': fao[yr],
                     'unit': 'kg/person/yr', 'index': 100 * fao[yr] / fao[2019]})
        rows.append({'food': label, 'year': yr, 'source': 'Supermarket sales (ABS)', 'value': a[FY[i]],
                     'unit': 'g/person/day', 'index': 100 * a[FY[i]] / a[FY[0]], 'fy': FY[i]})
save(pd.DataFrame(rows).round(1), 'supply_vs_sales.csv')

# ---------------------------------------------------------------- S3-S5 ABS production by state (2024-25)
def load_abs(f):
    xl = pd.ExcelFile(os.path.join(RAW, f)); out = []
    for sh in xl.sheet_names:
        if not sh.startswith('Table'):
            continue
        t = xl.parse(sh, header=None)
        hi = t.index[t.apply(lambda r: r.astype(str).str.contains('Data item').any(), axis=1)][0]
        h = [str(x) for x in t.iloc[hi]]; b = t.iloc[hi + 1:].copy(); b.columns = h
        code = [c for c in h if 'code' in c.lower()][0]
        b = b[pd.to_numeric(b[code], errors='coerce').notna()]
        yc = [c for c in h if re.match(r'20\d\d-\d\d', c)]
        mm = b.melt(id_vars=['Region', code, 'Data item'], value_vars=yc, var_name='year', value_name='value')
        mm.columns = ['region', 'code', 'item', 'year', 'value']
        mm['year'] = mm.year.str[:7]; mm['table'] = sh; mm['file'] = f
        out.append(mm)
    d = pd.concat(out); d['value'] = pd.to_numeric(d.value, errors='coerce'); return d

A = pd.concat([load_abs(f) for f in ['s3-production-crops-winter.xlsx', 's3-production-crops-summer.xlsx',
                                     's3-production-crops-sugarcane.xlsx', 's4-horticulture.xlsx', 's5-livestock.xlsx']])
v = A[(A.year == '2024-25') & (A.region != 'Australia') & A.item.str.contains(r'Local value|Farm gate value \(\$m\)')].copy()
v = v[~((v.file == 's5-livestock.xlsx') & v.table.isin(['Table 3', 'Table 4']))]
v = v[~((v.file == 's4-horticulture.xlsx') & v.table.isin(['Table 1', 'Table 5', 'Table 6']))]
v = v[~v.item.str.startswith('Wool')]


def food_group(r):
    if 'crops' in r['file']:
        return 'Sugarcane' if 'Sugar' in r['item'] else 'Grains, oilseeds & pulses'
    if 'horti' in r['file']:
        return {'Table 2': 'Fruit', 'Table 3': 'Vegetables', 'Table 4': 'Nuts'}[r['table']]
    return 'Milk' if 'Milk' in r['item'] else 'Meat (livestock sold)'


v['group'] = v.apply(food_group, axis=1)
v['aud_m'] = [x if '($m)' in i else x / 1e6 for x, i in zip(v.value, v.item)]
v['state'] = v.region.map(ABBR)
sg = v.groupby(['state', 'region', 'group']).aud_m.sum().reset_index()

# S7 population at 31 Dec 2024 (midpoint of 2024-25)
p = pd.read_excel(os.path.join(RAW, 's7-population.xlsx'), 'Data1', header=None)
names = p.iloc[0].tolist(); body = p.iloc[10:].copy(); body[0] = pd.to_datetime(body[0])
cols = {i: re.split(r';\s*', names[i])[2].strip() for i in range(1, len(names))
        if isinstance(names[i], str) and 'Persons' in names[i]}
pop = body.set_index(0)[list(cols)].rename(columns=cols).apply(pd.to_numeric).loc['2024-12-01']

st = sg.groupby(['state', 'region']).aud_m.sum().reset_index(name='food_value_m')
st['population'] = st.region.map(pop).astype(int)
st['value_per_person'] = (st.food_value_m * 1e6 / st.population).round(0)
top = sg.loc[sg.groupby('state').aud_m.idxmax()].set_index('state').group
st['largest_group'] = st.state.map(top)
st['food_value_m'] = st.food_value_m.round(0)
st['lon'] = st.state.map(lambda s: CENTRE[s][0]); st['lat'] = st.state.map(lambda s: CENTRE[s][1])
# VIC and TAS are too small for a two-line label, so theirs sit offshore.
OFFSHORE = {'VIC': (140.6, -40.4), 'TAS': (151.4, -42.4)}
st['label_inside'] = (~st.state.isin(OFFSHORE)).astype(int)
st['label_lon'] = [OFFSHORE.get(s, (x, y))[0] for s, x, y in zip(st.state, st.lon, st.lat)]
st['label_lat'] = [OFFSHORE.get(s, (x, y))[1] for s, x, y in zip(st.state, st.lon, st.lat)]
save(st.sort_values('value_per_person', ascending=False), 'state_per_person.csv')

sg['lon'] = sg.state.map(lambda s: CENTRE[s][0]); sg['lat'] = sg.state.map(lambda s: CENTRE[s][1])
sg['share'] = (100 * sg.aud_m / sg.groupby('group').aud_m.transform('sum')).round(1)
sg['aud_m'] = sg.aud_m.round(1)
save(sg[sg.aud_m > 0], 'state_groups.csv')

# ---------------------------------------------------------------- S6 trade partners (2024)
tr = pd.read_csv(os.path.join(RAW, 's6-trade-all-partners.csv'), encoding='latin1')
tr = tr[(tr.Year == 2024) & tr.Element.isin(['Export value', 'Import value'])]
# Food only: drop fibres, hides, tobacco and other non-food agricultural goods.
NON_FOOD = r'wool|cotton|hides|skins|tobacco|cigar|silk|jute|sisal|hair|rubber|feathers|tallow|cake of|bran|fodder|forage'
tr = tr[~tr.Item.str.contains(NON_FOOD, case=False)]
tr['m49'] = tr['Partner Country Code (M49)'].astype(str).str.strip("'").str.zfill(3)
tr['flow'] = tr.Element.str.replace(' value', 's')
by = tr.groupby(['flow', 'm49']).Value.sum().reset_index()
by['share'] = 100 * by.Value / by.groupby('flow').Value.transform('sum')
topitem = (tr.groupby(['flow', 'm49', 'Item']).Value.sum().reset_index()
           .sort_values('Value').groupby(['flow', 'm49']).tail(1).set_index(['flow', 'm49']).Item)
SHORT_ITEM = {'Meat of cattle boneless, fresh or chilled': 'Beef (boneless)', 'Meat of cattle with the bone, fresh or chilled': 'Beef',
              'Meat of pig boneless, fresh or chilled': 'Pork (boneless)', 'Food preparations n.e.c.': 'Processed food preparations',
              'Lentils, dry': 'Lentils', 'Chick peas, dry': 'Chickpeas', 'Rape or colza seed': 'Canola seed',
              'Rice, paddy (rice milled equivalent)': 'Rice', 'Cashew nuts, shelled': 'Cashews', 'Olive oil': 'Olive oil',
              'Wine': 'Wine', 'Wheat': 'Wheat', 'Barley': 'Barley', 'Sugar, refined': 'Sugar',
              'Undenatured ethyl alcohol of an alcoholic strength by volume of less than 80% vol; spirits, liqueurs and other spirituous beverages': 'Spirits'}
by['top_item'] = [topitem.get((f, c)) for f, c in zip(by.flow, by.m49)]
by['top_item'] = by.top_item.map(lambda s: SHORT_ITEM.get(s, s.split(',')[0][:30]))

# Flow map keeps 10 flows per direction so arcs stay legible: the 10 largest export markets, and for
# imports, Europe merged into one regional flow (its countries all share one corridor) plus the 9
# largest other sources.
EUROPE = {'008', '020', '040', '112', '056', '070', '100', '191', '203', '208', '233', '234', '246', '250',
          '276', '292', '300', '348', '352', '372', '380', '428', '438', '440', '442', '470', '492', '498',
          '499', '528', '578', '616', '620', '642', '643', '674', '688', '703', '705', '724', '752', '756',
          '804', '807', '826'}
EU_NAME = {'380': 'Italy', '250': 'France', '826': 'UK', '528': 'Netherlands', '724': 'Spain', '276': 'Germany',
           '208': 'Denmark', '372': 'Ireland', '056': 'Belgium', '300': 'Greece'}
imp = by[by.flow == 'Imports']
eu = imp[imp.m49.isin(EUROPE)].sort_values('Value', ascending=False)
eu_items = tr[(tr.flow == 'Imports') & tr.m49.isin(EUROPE)].groupby('Item').Value.sum().idxmax()
europe = pd.DataFrame([{'flow': 'Imports', 'm49': 'EUR', 'Value': eu.Value.sum(), 'share': eu.share.sum(),
                        'top_item': SHORT_ITEM.get(eu_items, eu_items.split(',')[0][:30]),
                        'members': ', '.join(f"{EU_NAME.get(c, c)} {v / 1e3:,.0f}" for c, v in zip(eu.m49, eu.Value) if c in EU_NAME)
                                   + f' and {len(eu) - sum(c in EU_NAME for c in eu.m49)} more'}])
by = pd.concat([by[by.flow == 'Exports'].sort_values('Value', ascending=False).head(10),
                pd.concat([imp[~imp.m49.isin(EUROPE)], europe]).sort_values('Value', ascending=False).head(10)])
by['members'] = by.get('members').fillna('')
PARTNER = {  # m49: (display name, lon, lat)
    '156': ('China', 104.2, 35.9), '840': ('United States', -98.6, 39.8), '392': ('Japan', 138.3, 36.2),
    '410': ('South Korea', 127.8, 36.4), '360': ('Indonesia', 113.9, -0.8), '554': ('New Zealand', 172.5, -41.5),
    '704': ('Vietnam', 106.3, 16.0), '608': ('Philippines', 122.0, 12.9), '356': ('India', 78.9, 21.5),
    '458': ('Malaysia', 102.0, 4.2), '784': ('UAE', 54.4, 24.0), '702': ('Singapore', 103.8, 1.35),
    '764': ('Thailand', 101.0, 15.9), '050': ('Bangladesh', 90.3, 23.7), '158': ('Taiwan', 121.0, 23.7),
    '380': ('Italy', 12.6, 42.8), '250': ('France', 2.2, 46.2), '826': ('United Kingdom', -2.0, 54.0),
    '528': ('Netherlands', 5.3, 52.1), '032': ('Argentina', -63.6, -38.4), '724': ('Spain', -3.7, 40.4),
    '344': ('Hong Kong', 114.2, 22.3), '682': ('Saudi Arabia', 45.1, 23.9), '586': ('Pakistan', 69.3, 30.4),
    '276': ('Germany', 10.4, 51.2), '208': ('Denmark', 9.5, 56.3), '124': ('Canada', -106.0, 56.0),
    '076': ('Brazil', -51.9, -14.2), '598': ('Papua New Guinea', 143.9, -6.3), '144': ('Sri Lanka', 80.7, 7.9),
    '484': ('Mexico', -102.5, 23.6), '372': ('Ireland', -8.0, 53.4), '300': ('Greece', 21.8, 39.1),
    '818': ('Egypt', 30.8, 26.8), '368': ('Iraq', 43.7, 33.2), '634': ('Qatar', 51.2, 25.3), '414': ('Kuwait', 47.5, 29.3),
    '104': ('Myanmar', 96.0, 21.0), '056': ('Belgium', 4.5, 50.5), '152': ('Chile', -71.5, -35.7),
    'EUR': ('Europe', 8.0, 48.0)}
by['partner'] = by.m49.map(lambda c: PARTNER[c][0])
by['lon'] = by.m49.map(lambda c: PARTNER[c][1]); by['lat'] = by.m49.map(lambda c: PARTNER[c][2])
by['usd_m'] = (by.Value / 1e3).round(0)
by['share'] = by.share.round(1)
by['rank'] = by.groupby('flow').Value.rank(ascending=False).astype(int)
# Which side of the circle the map label sits on, to avoid collisions in crowded regions
# ('none' = no label: the Philippines label would sit on the China export flow; its tooltip still works).
SIDE = {('Exports', 'China'): 'left', ('Exports', 'Japan'): 'right', ('Exports', 'Vietnam'): 'left',
        ('Exports', 'Philippines'): 'none', ('Exports', 'Indonesia'): 'right', ('Exports', 'New Zealand'): 'right',
        ('Imports', 'China'): 'left', ('Imports', 'Thailand'): 'left', ('Imports', 'Malaysia'): 'left',
        ('Imports', 'Singapore'): 'right', ('Imports', 'Italy'): 'right', ('Imports', 'New Zealand'): 'right'}
by['label_side'] = [SIDE.get((f, p), 'top') for f, p in zip(by.flow, by.partner)]
# Signed arc bend per flow (+ = clockwise, as a share of flow length). Chosen with an offline layout
# check (allowing for line width) so that no two flows cross, no flow edge passes within ~10 px of a
# node it doesn't connect to, no two flows share a corridor, and flows leave Australia >= 5 degrees apart.
BEND = {('Exports', 'China'): -0.35, ('Exports', 'United States'): -0.05, ('Exports', 'Japan'): -0.25,
        ('Exports', 'South Korea'): -0.25, ('Exports', 'Indonesia'): 0.05, ('Exports', 'New Zealand'): -0.05,
        ('Exports', 'Vietnam'): -0.1, ('Exports', 'Philippines'): -0.05, ('Exports', 'UAE'): 0.1,
        ('Exports', 'Malaysia'): 0.15,
        ('Imports', 'Europe'): 0.25, ('Imports', 'New Zealand'): -0.05, ('Imports', 'United States'): -0.05,
        ('Imports', 'China'): -0.25, ('Imports', 'Thailand'): -0.2, ('Imports', 'Malaysia'): 0.25,
        ('Imports', 'Singapore'): 0.05, ('Imports', 'India'): 0.3, ('Imports', 'Vietnam'): -0.25,
        ('Imports', 'Indonesia'): -0.05}
by['bend'] = [BEND[(f, p)] for f, p in zip(by.flow, by.partner)]
save(by[['flow', 'rank', 'partner', 'm49', 'lon', 'lat', 'usd_m', 'share', 'top_item', 'members', 'bend', 'label_side']],
     'trade_partners.csv')
print('trade totals US$bn:', (tr.groupby('flow').Value.sum() / 1e6).round(1).to_dict())

# ---------------------------------------------------------------- map geometry
for f in ['australia.json', 'world-atlas.json']:
    shutil.copy(os.path.join(RAW, f), os.path.join(OUT, f))
