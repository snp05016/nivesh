# Walk-Forward Plan

### Strategy: Expanding Window Cross-Validation

The current `walk_forward.py` implements an expanding window strategy:
- Fold 1: Train `≤2021`, Validate `2022`
- Fold 2: Train `≤2022`, Validate `2023`
- Fold 3: Train `≤2023`, Validate `2024`
- Fold 4: Train `≤2024`, Validate `2025`

### Advantages:
- Closely mirrors the reality of model deployment.
- Prevents lookahead bias mathematically (`date.dt.year <= train_end_year`).

### Deficiencies:
- **Gaping**: There is no gap between the end of train and start of val. If validation starts on Jan 1, 2022, the 20d forward return target for Dec 31, 2021 (in the train set) relies on closing prices in late Jan 2022. This means the train targets leak validation data!
- **Fix Required**: Add an embargo period equal to the prediction horizon (20 days). If the validation year is 2022, the train set must end on `2021-12-01` to ensure no 20d forward target bleeds into 2022.
