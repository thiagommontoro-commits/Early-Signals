        mapa_chaves = {"BRASIL": "BR", "ARGENTINA": "AR", "MEXICO": "MX", "COLOMBIA": "CO", "URUGUAY": "UY", "PERU": "PE", "CHILE": "CL", "BOLIVIA": "BO", "PARAGUAY": "PY"}
        for chave_ia, pais_code in mapa_chaves.items():
            lista_cards = dados_noticias.get(chave_ia, [])
            if lista_cards and len(lista_cards) == 4:
                noticias_por_pais[pais_code] = "".join([construir_card_noticia(item) for item in lista_cards])
    except Exception as e:
        print(f"Aviso de IA: O sistema irá utilizar o banco de segurança robusto de contingência. Erro: {e}")

    # Substituição limpa de blocos via colchetes imunes (Fim do MemoryError)
    for sigla_p, codigo_p in [("BR", "BR"), ("AR", "AR"), ("MX", "MX"), ("CO", "CO"), ("UY", "UY"), ("PE", "PE"), ("CL", "CL"), ("BO", "BO"), ("PY", "PY")]:
        html_finalizado = html_finalizado.replace(f"[[NOTICIAS_{sigla_p}]]", noticias_por_pais.get(codigo_p, ""))

    with open("index.html", "w", encoding="utf-8") as file:
        file.write(html_finalizado.strip())
        
    print("Sucesso! Painel atualizado e HTML guardado em index.html.")

if __name__ == "__main__":
    gerar_relatorio()
