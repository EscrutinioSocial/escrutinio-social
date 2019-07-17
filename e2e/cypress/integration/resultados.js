describe('Pagina de resultados', () => {
  beforeEach(() => cy.loginAsAdmin());

  it('resultados', () => {
    cy.visit('/elecciones/resultados/1');
    cy.contains('Resultados para Córdoba');
  });

});
