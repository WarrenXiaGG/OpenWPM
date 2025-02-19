import gzip
import csv
from typing import Iterator, Tuple, Optional


class CrUXData:
    def __init__(
        self,
        file_path: str,
        rank_filter: Optional[int] = None,
        partition: Optional[int] = None,
        ignoreUntil: Optional[str] = None,
    ):
        """
        Initialize the iterator with the path to the gzip file and an optional rank filter.

        :param file_path: Path to the gzip file containing the CrUX data.
        :param rank_filter: Optional rank to filter the data. Can be 1000, 10000, 100000, 1000000.
        :param partition: Optional partition to filter the data. Can be 0 or 1.
        :param ignoreUntil: Optional site to ignore until. Useful for resuming a crawl.
        """
        self.file_path = file_path
        self.rank_filter = rank_filter
        self.partition = int(partition)
        self.ignoreUntil = ignoreUntil

        if self.partition is not None and self.partition not in [0, 1]:
            raise ValueError("Partition must be 0 or 1")

    def __iter__(self) -> Iterator[str]:
        """
        Iterate over the CrUX data, yielding each row as a dictionary.

        :return: An iterator of dictionaries representing rows of CrUX data.
        """
        with gzip.open(self.file_path, "rt", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            line = 0

            if self.ignoreUntil is not None:
                for row in reader:
                    line += 1
                    if row["origin"] == self.ignoreUntil:
                        break

            for row in reader:
                if self.rank_filter is not None and int(row["rank"]) > self.rank_filter:
                    break
                if self.partition is not None and line % 2 != self.partition:
                    line += 1
                    continue

                line += 1
                yield row["origin"]


# Example usage
# crux_iterator = CrUXDataIterator('path_to_data.gz', rank_filter=1000)
# for site in crux_iterator:
#     print(site)

if __name__ == "__main__":
    # Path to the CrUX data file
    crux_data_path = "202310.csv.gz"

    # Initialize the iterator with the path to the CrUX data file and a rank filter
    crux_iterator = CrUXData(crux_data_path, rank_filter=1000, partition=0)

    # Iterate over the CrUX data and print each row
    for index, site in enumerate(crux_iterator):
        print(f"Site: {site}, Rank: {index}")
