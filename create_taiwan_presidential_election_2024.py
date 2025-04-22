import pandas as pd
import os
import re
import sqlite3

class CreateTaiwanElection2024DB:
    def __init__(self):
        file_names = os.listdir("data")
        county_names = []
        for file_name in file_names:
            if ".xlsx" in file_name:
                file_name_split = re.split("\\(|\\)", file_name)
                # print(file_name_split)
                county_names.append(file_name_split[1])
        self.county_names = county_names      

    def tidy_county_dataframe(self, county_name:str):
        file_path = f"data/總統-A05-4-候選人得票數一覽表-各投開票所({county_name}).xlsx"
        df = pd.read_excel(file_path, skiprows=[0, 3, 4])
        df = df.iloc[:, :6]
        # print(df.head()
        candidates_info = df.iloc[0, 3:].values.tolist()
        # print(candidates_info)
        df.columns = ['town', 'village', 'polling_place'] + candidates_info
        # print(df.head())
        df.loc[:, "town"] = df['town'].ffill()
        # print(df["town"].unique())
        df.loc[:, "town"] = df['town'].str.strip()
        # print(df["town"].unique())
        df = df.dropna()
        # print(df.head())
        df["polling_place"] = df["polling_place"].astype(int)
        # print(df.dtypes)
        id_variables = ["town", "village", "polling_place"]
        melted_df = pd.melt(df, id_vars=id_variables, var_name="candidate_info", value_name="votes")
        # print(melted_df)
        melted_df["county"] = county_name
        return melted_df

    def concat_country_dataframe(self):
        country_df = pd.DataFrame()
        for county_name in self.county_names:
            county_df = self.tidy_county_dataframe(county_name)
            country_df = pd.concat([country_df, county_df])
        country_df = country_df.reset_index(drop=True)
        numbers, candidates = [], []
        for ele in country_df["candidate_info"].str.split("\n"):
            number = re.sub("\\(|\\)","",ele[0])
            numbers.append(int(number))
            candidate = ele[1]+"/"+ele[2]
            candidates.append(candidate)
        presidential_votes = country_df.loc[:, ["county", "town", "village", "polling_place"]]
        presidential_votes["number"] = numbers
        presidential_votes["candidate"] = candidates
        presidential_votes["votes"] = country_df["votes"].values
        # print(presidential_votes)
        return presidential_votes
    
    def create_database(self):
        presidential_votes = self.concat_country_dataframe()

        polling_place_df = presidential_votes.groupby(["county", "town", "village", "polling_place"]).count().reset_index()
        polling_place_df = polling_place_df[["county", "town", "village", "polling_place"]]
        polling_place_df = polling_place_df.reset_index()
        polling_place_df["index"] = polling_place_df["index"]+1
        polling_place_df = polling_place_df.rename(columns={"index":"id"})
        # print(polling_place_df.head())

        candidates_df = presidential_votes.groupby(["number", "candidate"]).count().reset_index()
        candidates_df = candidates_df[["number", "candidate"]]
        candidates_df = candidates_df.reset_index()
        candidates_df["index"] = candidates_df["index"] + 1
        candidates_df = candidates_df.rename(columns={"index":"id"})
        # print(candidates_df)

        join_keys = ["county", "town", "village", "polling_place"]
        votes_df = pd.merge(presidential_votes, polling_place_df, left_on=join_keys, right_on=join_keys, how="left")
        votes_df = votes_df[["id", "number", "votes"]]
        votes_df = votes_df.rename(columns={"id": "polling_place_id", "number":"candidate_id"})
        # print(votes_df)

        connection = sqlite3.connect("data/taiwan_presidential_election_2024.db")
        polling_place_df.to_sql("polling_places", con=connection, if_exists="replace", index=False)
        candidates_df.to_sql("candidates", con=connection, if_exists="replace", index=False)
        votes_df.to_sql("votes", con=connection, if_exists="replace", index=False)

        cur = connection.cursor()
        
        drop_view_sql = """DROP VIEW IF EXISTS votes_by_village;"""
        create_view_sql = """
        CREATE VIEW votes_by_village AS 
        SELECT polling_places.county,
               polling_places.town,
               polling_places.village,
               candidates.number,
               candidates.candidate,
               SUM(votes.votes) AS sum_votes
        FROM votes
        LEFT JOIN polling_places
        ON votes.polling_place_id = polling_places.id
        LEFT JOIN candidates
        ON votes.candidate_id = candidates.id
        GROUP BY polling_places.county,
                 polling_places.town,
                 polling_places.village,
                 candidates.id;
        """
        cur.execute(drop_view_sql)
        cur.execute(create_view_sql)
        connection.close()

create_taiwan_election_2024_db = CreateTaiwanElection2024DB()
create_taiwan_election_2024_db.create_database()


        