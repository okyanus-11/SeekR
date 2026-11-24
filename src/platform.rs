//! Minimal Windows desktop integration: single-instance activation and a
//! global hotkey. Other platforms get no-op stubs so the crate stays
//! buildable and testable without a desktop session.

#[cfg(windows)]
mod imp {
    use std::ffi::c_void;

    type Hwnd = *mut c_void;
    type Bool = i32;
    type Uint = u32;

    const SW_SHOW: i32 = 5;
    const SW_RESTORE: i32 = 9;
    const MOD_ALT: Uint = 0x0001;
    const MOD_NOREPEAT: Uint = 0x4000;
    const VK_SPACE: Uint = 0x20;
    const WM_HOTKEY: Uint = 0x0312;
    const ERROR_ALREADY_EXISTS: u32 = 183;

    #[repr(C)]
    struct Point {
        x: i32,
        y: i32,
    }

    #[repr(C)]
    struct Msg {
        hwnd: Hwnd,
        message: Uint,
        w_param: usize,
        l_param: isize,
        time: u32,
        pt: Point,
    }

    #[link(name = "user32")]
    unsafe extern "system" {
        fn RegisterHotKey(hwnd: Hwnd, id: i32, modifiers: Uint, vk: Uint) -> Bool;
        fn GetMessageW(msg: *mut Msg, hwnd: Hwnd, filter_min: Uint, filter_max: Uint) -> Bool;
        fn PeekMessageW(msg: *mut Msg, hwnd: Hwnd, min: Uint, max: Uint, remove: Uint) -> Bool;
        fn FindWindowW(class_name: *const u16, window_name: *const u16) -> Hwnd;
        fn ShowWindow(hwnd: Hwnd, command: i32) -> Bool;
        fn SetForegroundWindow(hwnd: Hwnd) -> Bool;
    }

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreateMutexW(
            attributes: *mut c_void,
            initial_owner: Bool,
            name: *const u16,
        ) -> *mut c_void;
        fn GetLastError() -> u32;
    }

    fn wide(text: &str) -> Vec<u16> {
        text.encode_utf16().chain(std::iter::once(0)).collect()
    }

    /// Returns `false` when another SeekR instance already owns the
    /// single-instance mutex. That instance is brought to the foreground.
    pub fn ensure_single_instance(title: &str) -> bool {
        let name = wide("Local\\SeekR.SingleInstance.2");
        // The handle is intentionally kept for the whole process lifetime.
        let handle = unsafe { CreateMutexW(std::ptr::null_mut(), 0, name.as_ptr()) };
        if handle.is_null() {
            return true;
        }
        if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
            let title = wide(title);
            let window = unsafe { FindWindowW(std::ptr::null(), title.as_ptr()) };
            if !window.is_null() {
                unsafe {
                    ShowWindow(window, SW_RESTORE);
                    ShowWindow(window, SW_SHOW);
                    SetForegroundWindow(window);
                }
            }
            return false;
        }
        true
    }

    /// Spawn a thread that owns the global hotkey and calls `on_hotkey`
    /// (on that thread) every time it fires.
    pub fn spawn_hotkey<F>(on_hotkey: F)
    where
        F: Fn() + Send + 'static,
    {
        std::thread::Builder::new()
            .name("seekr-hotkey".into())
            .spawn(move || unsafe {
                let mut msg: Msg = std::mem::zeroed();
                // Creating the thread's message queue first is required before
                // RegisterHotKey can post WM_HOTKEY to this thread.
                PeekMessageW(&mut msg, std::ptr::null_mut(), 0, 0, 0);
                if RegisterHotKey(std::ptr::null_mut(), 1, MOD_ALT | MOD_NOREPEAT, VK_SPACE) == 0 {
                    eprintln!(
                        "SeekR: could not register the Alt+Space hotkey; another application may own it."
                    );
                    return;
                }
                while GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0) > 0 {
                    if msg.message == WM_HOTKEY {
                        on_hotkey();
                    }
                }
            })
            .ok();
    }
}

#[cfg(windows)]
pub use imp::{ensure_single_instance, spawn_hotkey};

/// Non-Windows builds have no single-instance mutex.
#[cfg(not(windows))]
pub fn ensure_single_instance(_title: &str) -> bool {
    true
}

/// Non-Windows builds have no global hotkey.
#[cfg(not(windows))]
pub fn spawn_hotkey<F>(_on_hotkey: F)
where
    F: Fn() + Send + 'static,
{
}

#[cfg(test)]
mod tests {
    #[test]
    fn single_instance_always_succeeds_without_another_owner() {
        // Windows: the first call in this process creates the mutex.
        assert!(super::ensure_single_instance("SeekR-test"));
    }
}
