def create_combined_hitter_valuations(league):
    import sys
    sys.path.append('python/general')
    import utilities
    sys.path.append('python/munging')
    sys.path.append('python/analysis')
    import calculations
    import create_combined

    assert league.league_name in ['SoS', 'Legacy']
    combined_hitters = create_combined.create_combined_hitters(league)
    combined_hitters['type']='B'

    combined_hitters['sample'] = combined_hitters.apply(lambda row: row.pa > 500, axis=1)
    for run in range(1,3):
        combined_hitters = calculations.calc_z(df=combined_hitters, ls=league, type='hitting')
        combined_hitters['sample'] = combined_hitters.apply(lambda row: row.zar > 0, axis=1)

    combined_hitters_600 = create_combined.create_combined_hitters(league, pa=600)
    combined_hitters_600['type']='B'
    combined_hitters_600 = combined_hitters_600.merge(combined_hitters[['fg_id', 'sample']], how='left', on='fg_id')
    combined_hitters_600 = calculations.calc_z(df=combined_hitters_600, ls=league, type='hitting')
    combined_hitters = combined_hitters.merge(combined_hitters_600[['fg_id', 'value']].rename(columns={'value':'value_600'}), how='left', on='fg_id')

    columns = ['name','fg_id','type','elig','pa',
               league.hitting_counting_stats,
               league.hitting_rate_stats,
               'zar','value','value_600']
    columns = utilities.flatten(columns)
    combined_hitters = combined_hitters[columns]
    return combined_hitters




def create_combined_pitcher_valuations(league):
    import sys
    sys.path.append('python/general')
    import utilities
    sys.path.append('python/munging')
    sys.path.append('python/analysis')
    import calculations
    import create_combined

    assert league.league_name in ['SoS', 'Legacy']
    combined_pitchers = create_combined.create_combined_pitchers(league)
    combined_pitchers['type']='P'

    if league.league_name == 'SoS':
        combined_pitchers['sample'] = combined_pitchers.apply(lambda row: row.qs > 10.0 or row.sv > 5 or row.hld > 5, axis=1)
    elif league.league_name == 'Legacy':
        combined_pitchers['sample'] = combined_pitchers.apply(lambda row: row.ip > 100.0 or row.svhld > 10, axis=1)

    for run in range(1,3):
        combined_pitchers = calculations.calc_z(df=combined_pitchers, ls=league, type='pitching')
        combined_pitchers['sample'] = combined_pitchers.apply(lambda row: row.zar > 0, axis=1)

    columns = ['name','fg_id','team','type','elig','ip',
               league.pitching_counting_stats,
               league.pitching_rate_stats,
               'zar','value','zar_skills','rank_sp','rank_rp']
    columns = utilities.flatten(columns)
    combined_pitchers = combined_pitchers[columns]
    return combined_pitchers



def create_combined_valuations(league):

    import sys
    sys.path.append('python/general')
    import postgres
    sys.path.append('python/munging')
    import player_names
    sys.path.append('python/analysis')
    import pandas as pd
    import format_gs
    import gspread
    import gspread_dataframe as gsdf
    import gspread_formatting as gsfmt

    assert league.league_name in ['SoS', 'Legacy']
    #league = 'SoS'
    #league = 'Legacy'

    bbdb = postgres.connect_to_bbdb()
    names = player_names.get_player_names()
    gc = gspread.service_account(filename='./bb-2021-2b810d2e3d25.json')
    #bb2021 = gc.open("BB 2021 " + league.league_name)
    bb2021 = gc.open("BB 2021 InSeason")

    combined_hitters = create_combined_hitter_valuations(league)
    combined_pitchers = create_combined_pitcher_valuations(league)

    hitter_projections = bb2021.worksheet('Hitter Projections - ' + league.league_name)
    bb2021.values_clear(hitter_projections.title + "!A:Z")
    gsdf.set_with_dataframe(hitter_projections, combined_hitters)
    hitter_projections.update
    format_gs.format_gs_all(league=league, ls=league, type='hitting')

    pitcher_projections = bb2021.worksheet('Pitcher Projections - ' + league.league_name)
    bb2021.values_clear(pitcher_projections.title + "!A:Z")
    gsdf.set_with_dataframe(pitcher_projections, combined_pitchers)
    pitcher_projections.update
    format_gs.format_gs_all(league=league.league_name, ls=league, type='pitching')

    combined = pd.concat(
        [combined_hitters[['name','fg_id','type','zar','value']],
        combined_pitchers[['name','fg_id','type','zar','value']]])
    combined = combined.sort_values(by='value', ascending=False)

    gs_combined = bb2021.worksheet('Combined Z')
    gsdf.set_with_dataframe(gs_combined, combined)
    gs_combined.update

    gsfmt.format_cell_range(
        gs_combined, 'D:E',
        gsfmt.CellFormat(numberFormat=gsfmt.NumberFormat(type='NUMBER', pattern='0.0')))



#create_combined_valuations(league='SoS')
#create_combined_valuations(league='Legacy')


def update_inseason_valuations(league_sos, league_legacy):
    import sys
    sys.path.append('python/general')
    import gs
    import utilities
    import postgres
    import pandas as pd
    import gspread
    import gspread_dataframe as gsdf

    sos_hitters = create_combined_hitter_valuations(league=league_sos) \
        .rename(columns={'zar': 'zar_sos', 'value': 'value_sos', 'value_600': 'value_600_sos'})
    legacy_hitters = create_combined_hitter_valuations(league=league_legacy) \
        .rename(columns={'zar': 'zar_legacy', 'value': 'value_legacy', 'value_600': 'value_600_legacy'})
    legacy_extra_columns = list(set(legacy_hitters.columns)
                                .difference(sos_hitters.columns))
    legacy_extra_columns = utilities.flatten(['fg_id', legacy_extra_columns])

    columns = ['name', 'fg_id', 'type', 'elig', 'pa',
               league_sos.hitting_counting_stats,
               league_sos.hitting_counting_stats,
               league_legacy.hitting_rate_stats,
               league_legacy.hitting_rate_stats,
               'zar_sos', 'value_sos', 'value_600_sos', 'zar_legacy', 'value_legacy', 'value_600_legacy']
    columns = utilities.flatten(columns)
    combined_hitters = sos_hitters.merge(legacy_hitters[legacy_extra_columns], on='fg_id')
    combined_hitters.drop_duplicates(subset=['fg_id'], inplace=True)

    # Merge in the ownership
    bbdb = postgres.connect_to_bbdb()
    sos_rosters = pd.read_sql('SELECT fg_id, sos."Team" FROM rosters.sos', con=bbdb)
    sos_rosters[['fg_id']] = sos_rosters[['fg_id']].astype(str)
    combined_hitters = combined_hitters.merge(sos_rosters, how='left', on='fg_id')

    legacy_rosters = pd.read_sql('SELECT fg_id, legacy."Team" as legacy_team FROM rosters.legacy', con=bbdb)
    legacy_rosters[['fg_id']] = legacy_rosters[['fg_id']].astype(str)
    combined_hitters = combined_hitters.merge(legacy_rosters, how='left', on='fg_id')


    # Pitchers
    sos_pitchers = create_combined_pitcher_valuations(league=league_sos) \
        .rename(columns={'zar': 'zar_sos', 'value': 'value_sos'})
    legacy_pitchers = create_combined_pitcher_valuations(league=league_legacy) \
        .rename(columns={'zar': 'zar_legacy', 'value': 'value_legacy'})
    legacy_extra_columns = list(set(legacy_pitchers.columns)
                                .difference(sos_pitchers.columns))
    legacy_extra_columns = utilities.flatten(['fg_id', legacy_extra_columns])

    columns = ['name', 'fg_id', 'type', 'ip',
               league_sos.pitching_counting_stats,
               league_legacy.pitching_counting_stats,
               league_sos.pitching_rate_stats,
               league_legacy.pitching_rate_stats,
               'zar_sos', 'value_sos', 'zar_legacy', 'value_legacy']
    columns = utilities.flatten(columns)
    combined_pitchers = sos_pitchers.merge(legacy_pitchers[legacy_extra_columns], on='fg_id')
    combined_pitchers = combined_pitchers[columns]

    bbdb = postgres.connect_to_bbdb()
    sos_rosters = pd.read_sql('SELECT * FROM rosters.sos', con=bbdb)
    sos_rosters = sos_rosters[['fg_id', 'Team']].rename(columns={'Team': 'sos_team'})
    sos_rosters[['fg_id']] = sos_rosters[['fg_id']].astype(str)

    combined_pitchers = combined_pitchers.merge(sos_rosters, how='left', on='fg_id')

    # Update Google Sheets
    gc = gspread.service_account(filename='./bb-2021-2b810d2e3d25.json')
    sh = gc.open("BB 2021 InSeason").worksheet('Proj - Hitters')
    gsdf.set_with_dataframe(sh, combined_hitters)
    gs.format_gsheet(sheet=sh)
    sh = gc.open("BB 2021 InSeason").worksheet('Proj - Pitchers')
    gsdf.set_with_dataframe(sh, combined_pitchers)
    gs.format_gsheet(sheet=sh)

