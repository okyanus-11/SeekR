fn main() {
    slint_build::compile("ui/launcher.slint")
        .expect("failed to compile the SeekR Slint interface");
}
