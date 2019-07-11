describe('Pagina de Login', function() {
    it('chequear web login', function() {
        cy.visit("/login/")
        cy.contains('Nombre de usuario o DNI')
  })
    it('chequear web fiscales', function() {
        cy.visit("/quiero-ser-fiscal/")
        cy.contains('Quiero ser fiscal de las PASO Nacional 2019')
  })

})