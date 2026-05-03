project('eta-right-click', 'c',
  version: '1.0.0',
  meson_version: '>= 0.50.0',
)

executable(
    'eta-click',
    'src/click.c',
    install: true,
    install_dir: get_option('bindir')
)

install_subdir(
    'src',
    install_dir: get_option('prefix') / 'eta-right-click',
    strip_directory: true
)


install_data(
    'data/default.conf',
    install_dir: '/etc/pardus',
    rename: 'eta-right-click.conf'
)

install_data(
    'data/eta-right-click.systemd',
    install_dir: '/lib/systemd/system',
    rename: 'eta-right-click.service'
)
