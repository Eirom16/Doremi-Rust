/// Single-pass QSS template engine using Aho-Corasick.
///
/// Replaces the chained `str.replace()` calls in Python's
/// `theme_manager.py`.  Instead of creating ~40 intermediate strings,
/// this scans the template **once** and substitutes all placeholders
/// simultaneously.

use std::collections::HashMap;

use aho_corasick::{AhoCorasick, Match, MatchKind};
use pyo3::prelude::*;

/// Process a QSS template string by replacing all placeholders in a
/// single pass using the Aho-Corasick algorithm.
///
/// Args:
///     template: The raw QSS string containing placeholder tokens
///               (e.g. `` "#A78BFA"``, ``"#0A0A14"``, …).
///     vars_map: A dictionary mapping **every** placeholder to its
///               replacement value.  Keys are matched literally
///               (case-sensitive).
///
/// Returns:
///     The fully-substituted QSS string.
///
/// Performance:
///     O(n + m) where n = template length, m = number of unique
///     placeholders.  The input template is scanned exactly once.
///     This avoids the 40+ intermediate string allocations that the
///     Python ``str.replace()`` chain created.
#[pyfunction]
pub fn process_qss_template(
    template: &str,
    vars_map: HashMap<String, String>,
) -> String {
    if vars_map.is_empty() {
        return template.to_string();
    }

    let patterns: Vec<&str> = vars_map.keys().map(|s| s.as_str()).collect();
    let ac = AhoCorasick::builder()
        .match_kind(MatchKind::LeftmostFirst)
        .build(&patterns)
        .expect("valid patterns");

    let mut result = String::with_capacity(template.len());

    let pat_ref = &patterns;
    let map_ref = &vars_map;

    ac.replace_all_with(template, &mut result, |m: &Match, _matched: &str, dst: &mut String| {
        let key = m.pattern().as_usize();
        if let Some(replacement) = map_ref.get(pat_ref[key]) {
            dst.push_str(replacement);
        }
        true
    });

    result
}
