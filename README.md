# MoneyMaul

A Six Nations Fantasy Rugby assistant for optimizing team selection and maximizing points.

## Features

- **Points Calculator** - Calculate fantasy points from match statistics
- **Team Validator** - Check budget, country limits, and squad requirements
- **Player Comparison** - Side-by-side stats analysis
- **Captain Recommender** - Data-driven captain picks
- **Transfer Suggestions** - Value-based player recommendations

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the app
streamlit run src/app/main.py

# Run tests
pytest tests/
```

## Project Structure

```
MoneyMaul/
├── src/
│   ├── scrapers/       # Data collection
│   ├── models/         # Data classes
│   ├── analysis/       # Points calc, recommendations
│   └── app/            # Streamlit pages
├── data/               # SQLite DB, cached data
├── tests/
└── requirements.txt
```

## Game Rules Summary

- **Budget**: 200 stars
- **Squad**: 15 players + optional Supersub
- **Country limit**: Max 4 players per nation
- **Captain**: 2x points
- **Supersub**: 3x if enters as sub, 0.5x otherwise

## License

MIT
