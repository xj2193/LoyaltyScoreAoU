from setuptools import setup, find_packages

setup(
    name="loyalty-score-aou",
    version="1.0.0",
    description="Loyalty Score prediction model for All of Us Research Program",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "google-cloud-bigquery",
        "pandas",
        "numpy",
        "scikit-learn",
        "jinja2",
    ],
)
