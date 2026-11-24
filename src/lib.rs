pub mod config;
pub mod platform;
pub mod search;

pub const PRODUCT_NAME: &str = "SeekR";

/// Version of the native Rust application. This is the 2.0.3 release target.
pub const PRODUCT_VERSION: &str = "2.0.3";

/// Last published Python/PySide6 release. It stays the supported fallback
/// download until the native build passes every release gate.
pub const LEGACY_RELEASE_VERSION: &str = "2.0.2";
