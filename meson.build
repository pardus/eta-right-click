project('eta-right-click', 'c',
  version: '1.0.0',
  meson_version: '>= 0.50.0',
)

executable(
    'eta-click',
    'src/click.c',
    dependencies: dependency('threads'),
    install: true,
    install_dir: get_option('bindir')
)

install_subdir(
    'src',
    install_dir: get_option('prefix') / 'share/eta/eta-right-click',
    strip_directory: true
)


install_data(
    'data/default.conf',
    install_dir: '/etc/pardus',
    rename: 'eta-right-click.conf'
)

install_data(
    'data/eta-right-click-settings.desktop',
    install_dir: get_option('prefix') / 'share/applications'
)

install_data(
    'data/tr.org.pardus.eta-right-click.policy',
    install_dir: get_option('prefix') / 'share/polkit-1/actions'
)

install_data(
    'data/eta-right-click-settings.svg',
    install_dir: get_option('prefix') / 'share/icons/hicolor/scalable/apps'
)

install_data(
    'data/eta-right-click.systemd',
    install_dir: '/lib/systemd/system',
    rename: 'eta-right-click.service'
)

install_data(
    'data/eta-click.systemd',
    install_dir: '/lib/systemd/system',
    rename: 'eta-click.service'
)
