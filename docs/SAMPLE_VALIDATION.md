# Independent spot checks — 28 October 2026

Executed DuckDB queries against the built database and compared the following 2024/25 domestic-league totals with league/club publications. These checks are not a representative accuracy audit.

| Player | Metric | Database | Published | Result |
|---|---|---:|---:|---|
| Mohamed Salah | Premier League goals | 29 | 29 | Match |
| Mohamed Salah | Premier League assists | 18 | 18 | Match |
| Harry Kane | Bundesliga goals | 26 | 26 | Match |
| Kylian Mbappé | La Liga goals | 31 | 31 | Match |
| Mateo Retegui | Serie A goals | 25 | 25 | Match |

Sources inspected through web search results:

- [Liverpool season-finale report](https://www.liverpoolfc.com/news/mohamed-salah-equals-premier-league-record-goal-involvements-season)
- [Bundesliga final top-scorer report](https://www.bundesliga.com/en/bundesliga/news/harry-kane-2024-25-top-scorer-second-time-bayern-munich-most-goals-award-32191)
- [Real Madrid Golden Boot report](https://www.realmadrid.com/en-US/news/football/first-team/latest-news/mbappe-bota-de-oro-2024-25-25-05-2025)
- [Atalanta season scoring report](https://en.atalanta.it/news/mateo-retegui-king-of-goals-crowned-best-striker-of-the-season)

Scope warning: Atalanta's pre-finale MVP announcement lists 7 assists and 35 appearances, while the full-season database lists 8 assists. Do not compare reports at different cutoff dates or treat this as proof of an error. Assists can also have provider-specific definitions. No adjustment was made.

Pending: a stratified 20-player comparison including transfers, goalkeepers, defenders, low-minute players and all five seasons; verify minutes and club-stint scope. The user’s full API-Football import is not available here. Current checks do not validate that wider sample, Ligue 1, or forecasting readiness.
