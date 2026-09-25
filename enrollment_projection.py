import pandas as pd
from pathlib import Path

pd.set_option("display.max_columns", None)

#  Load and prepare ACS enrollment data

raw_folder = Path("data/raw")
processed_folder = Path("data/processed")

processed_folder.mkdir(parents=True, exist_ok=True)

grade_variables = {
    "B14007_008E": 4,
    "B14007_009E": 5,
    "B14007_010E": 6,
    "B14007_011E": 7,
    "B14007_012E": 8,
    "B14007_013E": 9,
    "B14007_014E": 10,
    "B14007_015E": 11,
    "B14007_016E": 12
}

years = [2019, 2021, 2022, 2023, 2024]

all_years = []

for year in years:
    file_path = raw_folder / f"ACSDT1Y{year}.B14007-Data.csv"

    df = pd.read_csv(file_path)

    df = df[df["NAME"] != "Geographic Area Name"]

    columns_to_keep = [
        "GEO_ID",
        "NAME"
    ] + list(grade_variables.keys())

    df = df[columns_to_keep]

    for column in grade_variables.keys():
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["year"] = year

    all_years.append(df)

combined_df = pd.concat(all_years, ignore_index=True)

print(combined_df.head())
print(combined_df.tail())
print(combined_df.shape)

long_df = combined_df.melt(
    id_vars=["GEO_ID", "NAME", "year"],
    value_vars=list(grade_variables.keys()),
    var_name="acs_variable",
    value_name="enrollment"
)

long_df["grade"] = long_df["acs_variable"].map(grade_variables)

long_df = long_df[
    ["GEO_ID", "NAME", "year", "grade", "enrollment", "acs_variable"]
]

long_df = long_df.sort_values(
    by=["NAME", "year", "grade"]
).reset_index(drop=True)

print(long_df.head(20))
print(long_df.shape)

# changing from wide to "long format" which will  make interpolation, CSR, WACSR, filtering, plotting, and Power BI much easier

long_df = combined_df.melt(
    id_vars=["GEO_ID", "NAME", "year"],
    value_vars=list(grade_variables.keys()),
    var_name="acs_variable",
    value_name="enrollment"
)

long_df["grade"] = long_df["acs_variable"].map(grade_variables)

long_df = long_df[
    ["GEO_ID", "NAME", "year", "grade", "enrollment", "acs_variable"]
]

long_df = long_df.sort_values(
    by=["NAME", "year", "grade"]
).reset_index(drop=True)

print(long_df.head(20))
print(long_df.shape)

# Calculating the missing 2020 enrollment data. enrollment 2020= enrollment2019+enrollment2021/2

# Labeling the original Census observations
long_df["value_status"] = "Observed"

# Getting 2019 enrollment values
data_2019 = long_df[long_df["year"] == 2019].copy()

# Getting 2021 enrollment values
data_2021 = long_df[long_df["year"] == 2021].copy()

interpolation_df = data_2019.merge(
    data_2021,
    on=["GEO_ID", "NAME", "grade"],
    suffixes=("_2019", "_2021")
)

# Calculating missing data for year 2020
interpolation_df["enrollment"] = (
    interpolation_df["enrollment_2019"]
    + interpolation_df["enrollment_2021"]
) / 2


# Adding new rows:

interpolation_df["year"] = 2020
interpolation_df["value_status"] = "Interpolated"

interpolation_df["acs_variable"] = interpolation_df["acs_variable_2019"]

interpolation_df = interpolation_df[
    [
        "GEO_ID",
        "NAME",
        "year",
        "grade",
        "enrollment",
        "acs_variable",
        "value_status"
    ]
]


complete_df = pd.concat(
    [long_df, interpolation_df],
    ignore_index=True
)

complete_df = complete_df.sort_values(
    by=["NAME", "year", "grade"]
).reset_index(drop=True)

barnstable = complete_df[
    complete_df["NAME"] == "Barnstable County, Massachusetts"
]

print(barnstable.head(27))
print(complete_df.shape)

# -----------------------------------
# CSR TEST: Grade 11 to Grade 12
# -----------------------------------

grade_11 = complete_df[
    complete_df["grade"] == 11
].copy()

grade_12 = complete_df[
    complete_df["grade"] == 12
].copy()

grade_11["csr_year"] = grade_11["year"] + 1


#Matching Grade 11 with the following Grade 12
csr_11_12 = grade_11.merge(
    grade_12,
    left_on=["GEO_ID", "NAME", "csr_year"],
    right_on=["GEO_ID", "NAME", "year"],
    suffixes=("_grade11", "_grade12")
)

# Calculating CSR= Grade12t/Grade11t-1
csr_11_12["csr"] = (
    csr_11_12["enrollment_grade12"]
    / csr_11_12["enrollment_grade11"]
)

# Testing with Barnstable:
barnstable_csr = csr_11_12[
    csr_11_12["NAME"] == "Barnstable County, Massachusetts"
]

print(
    barnstable_csr[
        [
            "year_grade11",
            "enrollment_grade11",
            "year_grade12",
            "enrollment_grade12",
            "csr"
        ]
    ]
)

# -----------------------------------
# CALCULATING CSR FOR ALL GRADE TRANSITIONS
# -----------------------------------

csr_results = []

for starting_grade in range(4, 12):

    ending_grade = starting_grade + 1

    current_grade = complete_df[
        complete_df["grade"] == starting_grade
    ].copy()

    next_grade = complete_df[
        complete_df["grade"] == ending_grade
    ].copy()

    current_grade["csr_year"] = current_grade["year"] + 1

    transition_df = current_grade.merge(
        next_grade,
        left_on=["GEO_ID", "NAME", "csr_year"],
        right_on=["GEO_ID", "NAME", "year"],
        suffixes=("_start", "_end")
    )

    transition_df["csr"] = (
        transition_df["enrollment_end"]
        / transition_df["enrollment_start"]
    )

    transition_df["starting_grade"] = starting_grade
    transition_df["ending_grade"] = ending_grade

    transition_df = transition_df[
        [
            "GEO_ID",
            "NAME",
            "csr_year",
            "starting_grade",
            "ending_grade",
            "enrollment_start",
            "enrollment_end",
            "csr"
        ]
    ]

    csr_results.append(transition_df)

all_csr_df = pd.concat(
    csr_results,
    ignore_index=True
)

all_csr_df = all_csr_df.sort_values(
    by=["NAME", "starting_grade", "csr_year"]
).reset_index(drop=True)

print(all_csr_df.head(20))
print(all_csr_df.shape)


# -----------------------------------
# CALCULATING WACSR=(0.15×CSR2020+(0.15×CSR2021+(0.15×CSR2022)+(0.15×CSR2023)+(0.40×CSR2024)
# -----------------------------------

csr_weights = {
    2020: 0.15,
    2021: 0.15,
    2022: 0.15,
    2023: 0.15,
    2024: 0.40
}

all_csr_df["weight"] = all_csr_df["csr_year"].map(csr_weights)

all_csr_df["weighted_csr"] = (
    all_csr_df["csr"] * all_csr_df["weight"]
)


wacsr_df = (
    all_csr_df
    .groupby(
        [
            "GEO_ID",
            "NAME",
            "starting_grade",
            "ending_grade"
        ],
        as_index=False
    )["weighted_csr"]
    .sum()
)

wacsr_df = wacsr_df.rename(
    columns={"weighted_csr": "wacsr"}
)

print(wacsr_df.head(20))
print(wacsr_df.shape)

# TESTING Barnstable Grade 11→12 CSRs
barnstable_wacsr_check = wacsr_df[
    (wacsr_df["NAME"] == "Barnstable County, Massachusetts")
    & (wacsr_df["starting_grade"] == 11)
    & (wacsr_df["ending_grade"] == 12)
]

print(barnstable_wacsr_check)

# -----------------------------------
# PROJECT 2025 ENROLLMENT: Grade 11 in 2024 × the 11→12 WACSR = projected Grade 12 in 2025.
# -----------------------------------

# Getting the actual 2024 enrollment data
data_2024 = complete_df[
    complete_df["year"] == 2024
].copy()

# Matching each 2024 grade with the WACSR
projection_2025 = data_2024.merge(
    wacsr_df,
    left_on=["GEO_ID", "NAME", "grade"],
    right_on=["GEO_ID", "NAME", "starting_grade"]
)

# Calculating the next year's projected enrollment
projection_2025["projected_enrollment"] = (
    projection_2025["enrollment"]
    * projection_2025["wacsr"]
)

# The projected grade is the ending grade
projection_2025["projected_grade"] = projection_2025["ending_grade"]

# These projections are for 2025
projection_2025["projection_year"] = 2025


# Barnstable Projection 2025 testing:

barnstable_2025_check = projection_2025[
    (projection_2025["NAME"] == "Barnstable County, Massachusetts")
    & (projection_2025["projected_grade"] == 12)
]

print(
    barnstable_2025_check[
        [
            "NAME",
            "grade",
            "enrollment",
            "wacsr",
            "projected_grade",
            "projection_year",
            "projected_enrollment"
        ]
    ]
)

print(projection_2025.shape)

# -----------------------------------
# PROJECTING ENROLLMENT 2025-2029
# -----------------------------------

# Starting with the observed 2024 enrollment
current_projection = complete_df[
    complete_df["year"] == 2024
][
    ["GEO_ID", "NAME", "grade", "enrollment"]
].copy()

projection_results = []

for projection_year in range(2025, 2030):

    next_projection = current_projection.merge(
        wacsr_df,
        left_on=["GEO_ID", "NAME", "grade"],
        right_on=["GEO_ID", "NAME", "starting_grade"]
    )

    next_projection["projected_enrollment"] = (
        next_projection["enrollment"]
        * next_projection["wacsr"]
    )

    next_projection["grade"] = next_projection["ending_grade"]
    next_projection["year"] = projection_year
    next_projection["value_status"] = "Projected"

    projection_results.append(
        next_projection[
            [
                "GEO_ID",
                "NAME",
                "year",
                "grade",
                "projected_enrollment",
                "value_status"
            ]
        ].copy()
    )

    current_projection = next_projection[
        [
            "GEO_ID",
            "NAME",
            "grade",
            "projected_enrollment"
        ]
    ].copy()

    current_projection = current_projection.rename(
        columns={"projected_enrollment": "enrollment"}
    )


# Combining all five projections years

all_projections_df = pd.concat(
    projection_results,
    ignore_index=True
)

all_projections_df = all_projections_df.sort_values(
    by=["NAME", "year", "grade"]
).reset_index(drop=True)

print(all_projections_df.shape)

# Creating the actual High-school output grades 9-12:

high_school_projections = all_projections_df[
    all_projections_df["grade"].between(9, 12)
].copy()

high_school_projections = high_school_projections.sort_values(
    by=["NAME", "year", "grade"]
).reset_index(drop=True)

print(high_school_projections.head(20))
print(high_school_projections.shape)


# -----------------------------------
# SAVING PROCESSED DATASETS
# -----------------------------------

complete_df.to_csv(
    processed_folder / "historical_enrollment_2019_2024.csv",
    index=False
)

all_csr_df.to_csv(
    processed_folder / "cohort_survival_rates.csv",
    index=False
)

wacsr_df.to_csv(
    processed_folder / "weighted_cohort_survival_rates.csv",
    index=False
)

high_school_projections.to_csv(
    "output/high_school_enrollment_projections_2025_2029.csv",
    index=False
)

# -----------------------------------
# FINAL QUALITY ASSURANCE CHECKS
# -----------------------------------

print("\n--- FINAL QA CHECKS ---")

# A. Checking missing values
print("\nMissing values in historical data:")
print(complete_df.isna().sum())

print("\nMissing values in WACSR data:")
print(wacsr_df.isna().sum())

print("\nMissing values in final projections:")
print(high_school_projections.isna().sum())


# B. Checking duplicate county-year-grade records
historical_duplicates = complete_df.duplicated(
    subset=["GEO_ID", "year", "grade"]
).sum()

projection_duplicates = high_school_projections.duplicated(
    subset=["GEO_ID", "year", "grade"]
).sum()

print("\nHistorical duplicates:", historical_duplicates)
print("Projection duplicates:", projection_duplicates)


# C. Checking for impossible negative enrollment
historical_negative = (complete_df["enrollment"] < 0).sum()

projection_negative = (
    high_school_projections["projected_enrollment"] < 0
).sum()

print("\nNegative historical enrollments:", historical_negative)
print("Negative projected enrollments:", projection_negative)


# D. Examining CSR distribution
print("\nCSR summary:")
print(all_csr_df["csr"].describe())


# E. Examining WACSR distribution
print("\nWACSR summary:")
print(wacsr_df["wacsr"].describe())


# F. Identifying unusually large or small WACSR values
wacsr_review = wacsr_df[
    (wacsr_df["wacsr"] < 0.5)
    | (wacsr_df["wacsr"] > 1.5)
].copy()

print("\nWACSR values flagged for review:")
print(wacsr_review)


# I. Examining final projection distribution
print("\nProjected enrollment summary:")
print(
    high_school_projections["projected_enrollment"].describe()
)

# -----------------------------------
# INVESTIGATING FLAGGED WACSR VALUES
# -----------------------------------

print("\n--- INVESTIGATION OF FLAGGED WACSR VALUES ---")

flagged_csr_details = all_csr_df.merge(
    wacsr_review[
        ["GEO_ID", "starting_grade", "ending_grade"]
    ],
    on=["GEO_ID", "starting_grade", "ending_grade"],
    how="inner"
)

flagged_csr_details = flagged_csr_details.sort_values(
    by=["NAME", "starting_grade", "csr_year"]
)

print(
    flagged_csr_details[
        [
            "NAME",
            "csr_year",
            "starting_grade",
            "ending_grade",
            "enrollment_start",
            "enrollment_end",
            "csr"
        ]
    ].to_string(index=False)
)



# ---------------------------------------------------------
# FINAL QUALITY ASSURANCE SUMMARY
# ---------------------------------------------------------

# Counting how many historical observations were interpolated
interpolated_count = (
    complete_df["value_status"] == "Interpolated"
).sum()

# Counting missing values in the important datasets
historical_missing = complete_df.isnull().sum().sum()
wacsr_missing = wacsr_df.isnull().sum().sum()
projection_missing = high_school_projections.isnull().sum().sum()

# Counting duplicate county/year/grade records
historical_duplicates = complete_df.duplicated(
    subset=["GEO_ID", "year", "grade"]
).sum()

projection_duplicates = high_school_projections.duplicated(
    subset=["GEO_ID", "year", "grade"]
).sum()

# Counting negative enrollment values
negative_historical = (
    complete_df["enrollment"] < 0
).sum()

negative_projections = (
    high_school_projections["projected_enrollment"] < 0
).sum()

# Number of WACSR values already flagged by our QA rule
flagged_wacsr_count = len(wacsr_review)


print("\n--- FINAL QA SUMMARY ---")

print(f"Historical records: {len(complete_df)}")
print(f"Interpolated 2020 records: {interpolated_count}")
print(f"Missing historical values: {historical_missing}")
print(f"Duplicate historical records: {historical_duplicates}")
print(f"Negative historical enrollments: {negative_historical}")

print(f"\nCSR calculations: {len(all_csr_df)}")

print(f"\nWACSR calculations: {len(wacsr_df)}")
print(f"Missing WACSR values: {wacsr_missing}")
print(f"Flagged WACSR values: {flagged_wacsr_count}")

print(f"\nFinal projections: {len(high_school_projections)}")
print(f"Missing projection values: {projection_missing}")
print(f"Duplicate projection records: {projection_duplicates}")
print(f"Negative projected enrollments: {negative_projections}")

wacsr_review.to_csv(
    processed_folder / "wacsr_qa_flags.csv",
    index=False
)