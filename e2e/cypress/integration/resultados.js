describe('Pagina de resultados', () => {
  beforeEach(() => cy.loginAsAdmin());

  it('resultados', () => {
    cy.visit('/elecciones/resultados');
    cy.contains('Resultados para todo el país');
  });

});
