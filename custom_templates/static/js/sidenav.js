$(document).ready(function() {
  var $sideNavItems = $('#slide-out li a');
  var $sideNavItem = $('#slide-out li a:contains(Actuar sobre acta)');

  // Si el menu solo contiene actuar sobre acta
  // se oculta side nav
  if ($sideNavItems.length === 3 && $sideNavItem.length) {
    $('.sidenav').removeClass('sidenav-fixed');
    $('main').css('margin-left', 0);
  }

});
