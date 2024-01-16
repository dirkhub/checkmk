// Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
// conditions defined in the file COPYING, which is part of this source code package.

use super::sqls::{self, find_known_query};
use crate::config::{self, section, section::names};
use crate::emit::header;
use crate::{constants, utils};
use anyhow::Result;
use std::collections::HashMap;
use std::fs::read_to_string;
use std::path::PathBuf;

use tiberius::Row;

#[derive(Debug, PartialEq)]
pub enum SectionKind {
    Sync,
    Async,
}

#[derive(Debug, Clone)]
pub struct Section {
    name: String,
    sep: char,
    cache_age: Option<u32>,
}

impl Section {
    pub fn make_instance_section() -> Self {
        let config_section = config::section::SectionBuilder::new(section::names::INSTANCE).build();
        Self {
            name: config_section.name().to_string(),
            sep: config_section.sep(),
            cache_age: None,
        }
    }

    pub fn new(section: &config::section::Section, cache_age: u32) -> Self {
        let cache_age = if section.kind() == config::section::SectionKind::Async {
            Some(cache_age)
        } else {
            None
        };
        Self {
            name: section.name().into(),
            sep: section.sep(),
            cache_age,
        }
    }

    pub fn to_plain_header(&self) -> String {
        header(&self.name, self.sep)
    }

    pub fn to_work_header(&self) -> String {
        header(&(self.name.clone() + &self.cached_header()), self.sep)
    }

    fn cached_header(&self) -> String {
        self.cache_age
            .map(|age| {
                format!(
                    ":cached({},{})",
                    utils::get_utc_now().unwrap_or_default(),
                    age
                )
            })
            .unwrap_or_default()
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn sep(&self) -> char {
        self.sep
    }

    pub fn kind(&self) -> &SectionKind {
        if self.cache_age.is_some() {
            &SectionKind::Async
        } else {
            &SectionKind::Sync
        }
    }

    pub fn cache_age(&self) -> u32 {
        if let Some(v) = self.cache_age {
            v
        } else {
            0
        }
    }

    pub fn first_line<F>(&self, closure: F) -> String
    where
        F: Fn() -> String,
    {
        match self.name.as_ref() {
            section::names::JOBS | section::names::MIRRORING => closure(),
            _ => "".to_string(),
        }
    }

    pub fn select_query(&self, sql_dir: Option<PathBuf>) -> Option<String> {
        match self.name.as_ref() {
            names::INSTANCE => find_known_query(sqls::Id::InstanceProperties)
                .map(str::to_string)
                .ok(),
            _ => self.find_query(sql_dir),
        }
    }

    fn find_query(&self, sql_dir: Option<PathBuf>) -> Option<String> {
        self.find_provided_query(sql_dir).or_else(|| {
            get_sql_id(&self.name)
                .and_then(Self::find_known_query)
                .map(|s| s.to_owned())
        })
    }

    fn find_provided_query(&self, sql_dir: Option<PathBuf>) -> Option<String> {
        if let Some(dir) = sql_dir {
            let f = dir.join(self.name.to_lowercase().to_owned() + constants::SQL_QUERY_EXTENSION);
            read_to_string(&f)
                .map_err(|e| {
                    log::error!("Can't read file {:?} {}", &f, &e);
                    e
                })
                .ok()
        } else {
            None
        }
    }

    fn find_known_query(id: sqls::Id) -> Option<&'static str> {
        sqls::find_known_query(id)
            .map_err(|e| {
                log::error!("{e}");
                e
            })
            .ok()
    }

    pub fn main_db(&self) -> Option<String> {
        match self.name.as_ref() {
            section::names::JOBS => Some("msdb"),
            section::names::MIRRORING => Some("master"),
            _ => None,
        }
        .map(|s| s.to_string())
    }

    pub fn validate_rows(&self, rows: Vec<Vec<Row>>) -> Result<Vec<Vec<Row>>> {
        const ALLOW_TO_HAVE_EMPTY_OUTPUT: [&str; 2] = [
            section::names::MIRRORING,
            section::names::AVAILABILITY_GROUPS,
        ];
        if (!rows.is_empty() && !rows[0].is_empty())
            || (ALLOW_TO_HAVE_EMPTY_OUTPUT.contains(&self.name()))
        {
            Ok(rows)
        } else {
            log::warn!("No output from query");
            Err(anyhow::anyhow!("No output from query"))
        }
    }
}

lazy_static::lazy_static! {
    static ref SECTION_MAP: HashMap<&'static str, sqls::Id> = HashMap::from([
        (names::INSTANCE, sqls::Id::InstanceProperties),
        (names::COUNTERS, sqls::Id::Counters),
        (names::BACKUP, sqls::Id::Backup),
        (names::BLOCKED_SESSIONS, sqls::Id::BlockedSessions),
        (names::DATABASES, sqls::Id::Databases),
        (names::CONNECTIONS, sqls::Id::Connections),

        (names::TRANSACTION_LOG, sqls::Id::TransactionLogs),
        (names::DATAFILES, sqls::Id::Datafiles),
        (names::TABLE_SPACES, sqls::Id::TableSpaces),
        (names::CLUSTERS, sqls::Id::Clusters),

        (names::JOBS, sqls::Id::Jobs),
        (names::MIRRORING, sqls::Id::Mirroring),
        (names::AVAILABILITY_GROUPS, sqls::Id::AvailabilityGroups),
    ]);
}

pub fn get_sql_id<T: AsRef<str>>(section_name: T) -> Option<sqls::Id> {
    SECTION_MAP.get(section_name.as_ref()).copied()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::ms_sql::Config;
    use crate::config::section;
    use crate::ms_sql::custom;

    #[test]
    fn test_section_header() {
        let section = Section::make_instance_section();
        assert_eq!(section.to_plain_header(), "<<<mssql_instance:sep(124)>>>\n");
        assert_eq!(section.to_work_header(), "<<<mssql_instance:sep(124)>>>\n");

        let section = Section::new(
            &section::SectionBuilder::new("backup").set_async().build(),
            100,
        );
        assert_eq!(section.to_plain_header(), "<<<mssql_backup:sep(124)>>>\n");
        assert!(section
            .to_work_header()
            .starts_with("<<<mssql_backup:cached("));
        assert!(section.to_work_header().ends_with("100):sep(124)>>>\n"));
    }

    #[test]
    fn test_section_select_query() {
        let mk_section =
            |name: &str| Section::new(&config::section::SectionBuilder::new(name).build(), 100);
        let test_set: &[(&str, sqls::Id)] = &[
            (names::INSTANCE, sqls::Id::InstanceProperties),
            (names::DATABASES, sqls::Id::Databases),
            (names::COUNTERS, sqls::Id::Counters),
            (names::BLOCKED_SESSIONS, sqls::Id::BlockedSessions),
            (names::TRANSACTION_LOG, sqls::Id::TransactionLogs),
            (names::CLUSTERS, sqls::Id::Clusters),
            (names::MIRRORING, sqls::Id::Mirroring),
            (names::AVAILABILITY_GROUPS, sqls::Id::AvailabilityGroups),
            (names::CONNECTIONS, sqls::Id::Connections),
            (names::TABLE_SPACES, sqls::Id::TableSpaces),
            (names::DATAFILES, sqls::Id::Datafiles),
            (names::BACKUP, sqls::Id::Backup),
            (names::JOBS, sqls::Id::Jobs),
        ];
        for (name, ids) in test_set {
            assert_eq!(
                mk_section(name)
                    .select_query(custom::get_sql_dir())
                    .unwrap(),
                find_known_query(ids).unwrap()
            );
        }
        assert_eq!(
            mk_section("no_name").select_query(custom::get_sql_dir()),
            None
        )
    }

    #[test]
    fn test_work_sections() {
        let config = Config::default();
        assert_eq!(config.all_sections().len(), 13);
    }

    /// We test only few parameters
    #[test]
    fn test_get_ids() {
        assert_eq!(get_sql_id(names::JOBS).unwrap(), sqls::Id::Jobs);
        assert_eq!(
            get_sql_id(section::names::MIRRORING).unwrap(),
            sqls::Id::Mirroring
        );
        assert_eq!(
            get_sql_id(names::AVAILABILITY_GROUPS).unwrap(),
            sqls::Id::AvailabilityGroups
        );
        assert_eq!(get_sql_id(names::COUNTERS).unwrap(), sqls::Id::Counters);
        assert_eq!(get_sql_id(names::CLUSTERS).unwrap(), sqls::Id::Clusters);
        assert_eq!(
            get_sql_id(names::CONNECTIONS).unwrap(),
            sqls::Id::Connections
        );
        assert!(get_sql_id("").is_none());
    }
}
