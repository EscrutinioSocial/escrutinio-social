describe('Pagina de Login', () => {
  it('chequear web login', () => {
    cy.visit('/login/');
    cy.contains('Nombre de usuario o DNI');
  });

  it('chequear web fiscales', () => {
    cy.visit('/quiero-ser-fiscal/');
    cy.contains('Quiero ser fiscal de las PASO Nacional 2019');
  });

  it('login', () => {
    cy.visit('/login/');
    cy.get('#id_username').type('admin');
    cy.get('#id_password').first().focus();
    cy.get('#id_password').type('admin');
    cy.contains('Identificarse').click();
    cy.contains('Cargar resultados de actas');
  });

});
