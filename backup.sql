--
-- PostgreSQL database dump
--

\restrict gUtUPMdC1nOKhJdP46hKaEN16C3Medt3wMl6wCzEGaZQeXBanRbsGzPAfEhhDBY

-- Dumped from database version 18.3 (Debian 18.3-1.pgdg13+1)
-- Dumped by pg_dump version 18.3 (Debian 18.3-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: contatos; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.contatos (
    contato_id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid,
    nome character varying(255) NOT NULL,
    funcao character varying(100),
    email character varying(255),
    celular character varying(20),
    observacoes text,
    prioridade character varying(20),
    data_criacao timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.contatos OWNER TO admin;

--
-- Name: empresas; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.empresas (
    empresa_id uuid DEFAULT gen_random_uuid() NOT NULL,
    nome character varying(255) NOT NULL,
    segmento character varying(100),
    porte character varying(50),
    cidade character varying(100),
    endereco character varying(255),
    cep character varying(20),
    bairro character varying(100),
    regiao character varying(100),
    observacoes text
);


ALTER TABLE public.empresas OWNER TO admin;

--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.usuarios (
    usuario_id uuid DEFAULT gen_random_uuid() NOT NULL,
    nome character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    senha_hash text,
    telefone character varying(20),
    whatsapp character varying(20),
    data_nascimento date,
    especialidade character varying(100),
    cargo character varying(50),
    segmento_foco character varying(100),
    regiao character varying(100),
    meta_mensal numeric(10,2),
    taxa_comissao numeric(5,2),
    nivel_acesso character varying(20) DEFAULT 'vendedor'::character varying,
    ativo boolean DEFAULT true,
    data_criacao timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    ultimo_login timestamp without time zone,
    token_ativacao character varying(255),
    email_verificado boolean DEFAULT false,
    data_token timestamp without time zone
);


ALTER TABLE public.usuarios OWNER TO admin;

--
-- Data for Name: contatos; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.contatos (contato_id, empresa_id, nome, funcao, email, celular, observacoes, prioridade, data_criacao) FROM stdin;
2be5c52c-851b-4793-976f-243e8c6caca8	c3184baf-791c-44aa-928b-16efb60ed770	fabiana	comercial	comercial.red@gmail.com	4199999999	sou foda	media	2026-04-21 20:43:00.385626
\.


--
-- Data for Name: empresas; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.empresas (empresa_id, nome, segmento, porte, cidade, endereco, cep, bairro, regiao, observacoes) FROM stdin;
c3184baf-791c-44aa-928b-16efb60ed770	Gado certo	Venda de Gado	Medio	Curitiba	centro	83504000	centro	sul	bem observado
057abaa6-27dd-430a-8fc7-4d69b0064dac	Energydrive	\N	\N		\N	\N	\N	\N	\N
507e7b4d-041d-488f-a351-a73e0db453bd	Lenovo	\N	\N		\N	\N	\N	\N	\N
9eae2e7e-2508-4d6f-b730-e33de48529e1	KKKKKK	\N	\N	\N	\N	\N	\N	\N	\N
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.usuarios (usuario_id, nome, email, senha_hash, telefone, whatsapp, data_nascimento, especialidade, cargo, segmento_foco, regiao, meta_mensal, taxa_comissao, nivel_acesso, ativo, data_criacao, ultimo_login, token_ativacao, email_verificado, data_token) FROM stdin;
8b3ef112-8667-42ca-bb5c-fa2986143cf7	Gabriel Santos	gabrielsantos2411.gs@gmail.com	$2b$12$6vs37kwOTbXM6NLbIwf4hecxMVQEvItVex7MwYjXen8aGHscDfIlm	41998866661	\N	\N	\N	\N	\N	\N	\N	\N	vendedor	t	2026-04-22 20:58:46.947354	\N	\N	f	\N
\.


--
-- Name: contatos contatos_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.contatos
    ADD CONSTRAINT contatos_pkey PRIMARY KEY (contato_id);


--
-- Name: empresas empresas_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.empresas
    ADD CONSTRAINT empresas_pkey PRIMARY KEY (empresa_id);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (usuario_id);


--
-- Name: contatos contatos_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.contatos
    ADD CONSTRAINT contatos_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(empresa_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict gUtUPMdC1nOKhJdP46hKaEN16C3Medt3wMl6wCzEGaZQeXBanRbsGzPAfEhhDBY

